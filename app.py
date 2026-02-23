import io

from flask import Flask, render_template, redirect, url_for, flash, request, session, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import Babel, gettext, lazy_gettext
from config import Config
from models import db, User, Group, GroupMember, GroupInvitation, Event, EventResponse, Tag, GroupTag, EventTag, GroupInviteToken
from models import Notification, AuditLog, utcnow
from forms import LoginForm, RegistrationForm, GroupForm, InviteUserForm, EventForm, AccountDeleteForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from datetime import datetime, timedelta, timezone
import secrets
import re
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from flask import Response

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Initialize Babel for internationalization
babel = Babel(app)


def get_locale():
    """Determine the best match for supported languages"""
    supported = set(app.config['LANGUAGES'].keys())
    if current_user.is_authenticated and getattr(current_user, 'language', None) in supported:
        return current_user.language
    if session.get('language') in supported:
        return session['language']
    return request.accept_languages.best_match(supported)


babel.init_app(app, locale_selector=get_locale)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger('groupdoo')


def log_audit(event_type, message, user_id=None):
    """Persist audit events for security-sensitive actions"""
    ip_address = request.remote_addr
    db.session.add(AuditLog(
        user_id=user_id,
        event_type=event_type,
        message=message,
        ip_address=ip_address
    ))


def now_utc():
    """Timezone-aware UTC now"""
    return datetime.now(timezone.utc)


def to_utc(dt_value):
    """Ensure a datetime is timezone-aware in UTC"""
    if dt_value is None:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


@app.after_request
def add_security_headers(response):
    """Add basic security headers"""
    if app.config.get('SECURITY_HEADERS_ENABLE', True):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
            "img-src 'self' data: https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net"
        )
        if app.config.get('SECURITY_HEADERS_HSTS') and app.config.get('SESSION_COOKIE_SECURE'):
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response


# Helper functions for tag management
def add_tags_to_object(obj, tags_str, tag_model_class):
    """
    Add tags to a group or event.

    Args:
        obj: Group or Event object to add tags to
        tags_str: Comma-separated string of tag names
        tag_model_class: GroupTag or EventTag model class
    """
    if not tags_str:
        return

    # Parse tag names from comma-separated string
    tag_names = [name.strip() for name in tags_str.split(',') if name.strip()]

    for tag_name in tag_names:
        # Get or create the tag
        tag = Tag.query.filter_by(name=tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            db.session.add(tag)
            db.session.flush()  # Flush to get the tag ID without committing

        # Create the association (GroupTag or EventTag)
        if tag_model_class == GroupTag:
            tag_assoc = GroupTag(group_id=obj.id, tag_id=tag.id)
        else:  # EventTag
            tag_assoc = EventTag(event_id=obj.id, tag_id=tag.id)

        db.session.add(tag_assoc)


def remove_tags_from_object(obj, tag_model_class):
    """
    Remove all tags from a group or event.

    Args:
        obj: Group or Event object to remove tags from
        tag_model_class: GroupTag or EventTag model class
    """
    if tag_model_class == GroupTag:
        tag_assocs = GroupTag.query.filter_by(group_id=obj.id).all()
    else:  # EventTag
        tag_assocs = EventTag.query.filter_by(event_id=obj.id).all()

    for tag_assoc in tag_assocs:
        db.session.delete(tag_assoc)


def create_event_form():
    """Create EventForm with dynamically populated category and space choices from config"""
    form = EventForm()
    # Populate category choices from config
    form.category.choices = [('', 'Uncategorised')] + [(cat, cat) for cat in app.config['EVENT_CATEGORIES']]
    # Populate space choices from config
    form.space.choices = [('', 'Not specified')] + [(space, space) for space in app.config['EVENT_SPACES']]
    return form


def create_group_form():
    """Create GroupForm with dynamically populated invite method choices from config"""
    form = GroupForm()
    method_labels = app.config['GROUP_INVITE_METHOD_LABELS']
    form.invite_method.choices = [
        (method, method_labels.get(method, method))
        for method in app.config['GROUP_INVITE_METHODS']
    ]
    return form


def build_event_change_message(event_name, changes):
    """Build a notification message for event updates"""
    return f'Event "{event_name}" updated: ' + '; '.join(changes) + '. Please check if you can still attend.'


def _escape_ics_text(value):
    """Escape text for iCalendar fields"""
    if value is None:
        return ''
    return (str(value)
            .replace('\\', '\\\\')
            .replace(';', '\\;')
            .replace(',', '\\,')
            .replace('\r\n', '\\n')
            .replace('\n', '\\n'))


def _format_ics_datetime(value):
    """Format datetime for iCalendar (floating time)"""
    return value.strftime('%Y%m%dT%H%M%S')


def build_event_ics(event, event_url):
    """Build an iCalendar payload for an event"""
    dt_start = _format_ics_datetime(to_utc(event.event_date))
    dt_end = _format_ics_datetime(to_utc(event.event_date) + timedelta(hours=1))
    dt_stamp = _format_ics_datetime(now_utc())
    description_parts = []
    if event.description:
        description_parts.append(event.description)
    description_parts.append(f'Location: {event.location_name}, {event.address}')
    description_parts.append(f'Event page: {event_url}')
    if event.url:
        description_parts.append(f'Event link: {event.url}')
    description = _escape_ics_text('\n'.join(description_parts))
    location = _escape_ics_text(f'{event.location_name}, {event.address}')
    summary = _escape_ics_text(event.name)
    uid = _escape_ics_text(f'groupdoo-event-{event.id}@{request.host}')

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Groupdoo//EN',
        'CALSCALE:GREGORIAN',
        'BEGIN:VEVENT',
        f'UID:{uid}',
        f'DTSTAMP:{dt_stamp}',
        f'DTSTART:{dt_start}',
        f'DTEND:{dt_end}',
        f'SUMMARY:{summary}',
        f'DESCRIPTION:{description}',
        f'LOCATION:{location}',
        f'URL:{_escape_ics_text(event_url)}',
        'END:VEVENT',
        'END:VCALENDAR'
    ]
    return '\r\n'.join(lines) + '\r\n'


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return db.session.get(User, int(user_id))


# Context processor to make pending invitations count available in all templates
@app.context_processor
def inject_invitation_count():
    """Inject pending invitation count into all templates"""
    if current_user.is_authenticated:
        preferred_language = current_user.language or session.get('language') or app.config['BABEL_DEFAULT_LOCALE']
        if preferred_language not in app.config['LANGUAGES']:
            preferred_language = app.config['BABEL_DEFAULT_LOCALE']
        return {
            'pending_invitation_count': current_user.get_pending_invitation_count(),
            'currency_symbol': app.config['CURRENCY_SYMBOL'],
            'currency_code': app.config['CURRENCY_CODE'],
            'languages': app.config['LANGUAGES'],
            'current_language': preferred_language
        }
    return {
        'pending_invitation_count': 0,
        'currency_symbol': app.config['CURRENCY_SYMBOL'],
        'currency_code': app.config['CURRENCY_CODE'],
        'languages': app.config['LANGUAGES'],
        'current_language': session.get('language', app.config['BABEL_DEFAULT_LOCALE'])
    }


@app.route('/set_language/<language>')
def set_language(language):
    """Set the user's language preference"""
    if language in app.config['LANGUAGES']:
        session['language'] = language
        if current_user.is_authenticated:
            current_user.language = language
            db.session.commit()
        flash(gettext('Language changed successfully.'), 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """User login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.locked_until and user.locked_until > now_utc():
            flash('Account is temporarily locked due to failed login attempts. Try again later.', 'danger')
            log_audit('login_locked', f'Locked login attempt for {user.username}', user_id=user.id)
            db.session.commit()
            return redirect(url_for('login'))

        if user is None or not user.check_password(form.password.data):
            if user:
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= app.config['LOCKOUT_MAX_ATTEMPTS']:
                    user.locked_until = now_utc() + timedelta(minutes=app.config['LOCKOUT_MINUTES'])
                    log_audit('login_lockout', f'Account locked for {user.username}', user_id=user.id)
                else:
                    log_audit('login_failed', f'Failed login for {user.username}', user_id=user.id)
                db.session.commit()
            flash('Invalid username or password', 'danger')
            return redirect(url_for('login'))

        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        log_audit('login_success', f'Successful login for {user.username}', user_id=user.id)
        db.session.commit()

        login_user(user, remember=form.remember_me.data)
        session['language'] = user.language or session.get('language') or app.config['BABEL_DEFAULT_LOCALE']
        flash(f'Welcome back, {user.username}!', 'success')

        # Redirect to next page if it exists, otherwise to dashboard
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('dashboard')
        return redirect(next_page)

    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def register():
    """User registration page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Congratulations, you are now registered! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard (protected route)"""
    # Get user's owned groups
    owned_groups = current_user.owned_groups.all()

    # Get user's member groups
    memberships = current_user.group_memberships.all()
    member_groups = [m.group for m in memberships]

    # Get pending invitations
    pending_invitations = current_user.get_pending_invitations()

    # Get upcoming events from all user's groups
    all_user_groups = owned_groups + member_groups
    group_ids = [g.id for g in all_user_groups]

    # Get upcoming events (future events only) ordered by date
    upcoming_events = []
    if group_ids:
        upcoming_events = Event.query.filter(
            Event.group_id.in_(group_ids),
            Event.event_date > now_utc()
        ).order_by(Event.event_date.asc()).limit(10).all()

    notifications = current_user.notifications.filter_by(is_read=False).order_by(Notification.created_at.desc()).limit(10).all()

    return render_template('dashboard.html',
                         owned_groups=owned_groups,
                         member_groups=member_groups,
                         pending_invitations=pending_invitations,
                         upcoming_events=upcoming_events,
                         notifications=notifications,
                         current_time=now_utc())


@app.route('/search')
def search():
    """Search groups and events by free text and tags"""
    query = (request.args.get('q') or '').strip()
    member_groups = []
    member_events = []
    public_groups = []
    public_events = []

    if query:
        like = f"%{query}%"

        if current_user.is_authenticated:
            owned_groups = current_user.owned_groups.all()
            memberships = current_user.group_memberships.all()
            member_group_ids = {g.id for g in owned_groups} | {m.group_id for m in memberships}

            if member_group_ids:
                member_groups = Group.query \
                    .outerjoin(GroupTag, GroupTag.group_id == Group.id) \
                    .outerjoin(Tag, Tag.id == GroupTag.tag_id) \
                    .filter(Group.id.in_(member_group_ids)) \
                    .filter(or_(
                        Group.name.ilike(like),
                        Group.description.ilike(like),
                        Tag.name.ilike(like)
                    )) \
                    .distinct().all()

                member_events = Event.query \
                    .outerjoin(EventTag, EventTag.event_id == Event.id) \
                    .outerjoin(Tag, Tag.id == EventTag.tag_id) \
                    .filter(Event.group_id.in_(member_group_ids)) \
                    .filter(or_(
                        Event.name.ilike(like),
                        Event.description.ilike(like),
                        Tag.name.ilike(like)
                    )) \
                    .distinct().all()

        public_group_query = Group.query \
            .outerjoin(GroupTag, GroupTag.group_id == Group.id) \
            .outerjoin(Tag, Tag.id == GroupTag.tag_id) \
            .filter(Group.is_public.is_(True))

        if current_user.is_authenticated:
            owned_groups = current_user.owned_groups.all()
            memberships = current_user.group_memberships.all()
            member_group_ids = {g.id for g in owned_groups} | {m.group_id for m in memberships}
            if member_group_ids:
                public_group_query = public_group_query.filter(~Group.id.in_(member_group_ids))

        public_groups = public_group_query \
            .filter(or_(
                Group.name.ilike(like),
                Group.description.ilike(like),
                Tag.name.ilike(like)
            )) \
            .distinct().all()

        public_event_query = Event.query \
            .outerjoin(EventTag, EventTag.event_id == Event.id) \
            .outerjoin(Tag, Tag.id == EventTag.tag_id) \
            .join(Group, Event.group_id == Group.id) \
            .filter(Group.is_public.is_(True))

        if current_user.is_authenticated and 'member_group_ids' in locals() and member_group_ids:
            public_event_query = public_event_query.filter(~Event.group_id.in_(member_group_ids))

        public_events = public_event_query \
            .filter(or_(
                Event.name.ilike(like),
                Event.description.ilike(like),
                Tag.name.ilike(like)
            )) \
            .distinct().all()

    return render_template(
        'search.html',
        query=query,
        member_groups=member_groups,
        member_events=member_events,
        public_groups=public_groups,
        public_events=public_events
    )


@app.route('/notifications/<int:notification_id>/dismiss', methods=['POST'])
@login_required
def notification_dismiss(notification_id):
    """Dismiss a notification (mark as read)"""
    notification = Notification.query.get_or_404(notification_id)

    if notification.user_id != current_user.id:
        flash('You do not have permission to dismiss this notification.', 'danger')
        return redirect(url_for('dashboard'))

    notification.is_read = True
    db.session.commit()

    flash('Notification dismissed.', 'info')
    return redirect(url_for('dashboard'))


# Group Routes

@app.route('/groups')
@login_required
def groups_list():
    """List all public groups"""
    public_groups = Group.query.filter_by(is_public=True).order_by(Group.created_at.desc()).all()
    return render_template('groups/list.html', groups=public_groups)


@app.route('/groups/create', methods=['GET', 'POST'])
@login_required
def group_create():
    """Create a new group"""
    form = create_group_form()
    if form.validate_on_submit():
        group = Group(
            name=form.name.data,
            slug=generate_unique_slug(Group, slugify(form.name.data)),
            description=form.description.data,
            group_type=form.group_type.data,
            is_public=form.is_public.data,
            owner_id=current_user.id,
            invite_method=form.invite_method.data or app.config['GROUP_INVITE_METHOD_DEFAULT']
        )
        db.session.add(group)
        db.session.commit()

        # Add creator as a member and admin
        membership = GroupMember(group_id=group.id, user_id=current_user.id, role='admin')
        db.session.add(membership)
        db.session.commit()

        # Add tags if provided
        if form.tags.data:
            add_tags_to_object(group, form.tags.data, GroupTag)
            db.session.commit()

        flash(f'Group "{group.name}" created successfully!', 'success')
        return redirect(url_for('group_view', group_id=group.id))

    return render_template('groups/create.html', form=form)


@app.route('/groups/<int:group_id>')
def group_view(group_id):
    """View a group"""
    group = Group.query.get_or_404(group_id)

    # Check if user can view this group
    if not group.can_view(current_user):
        flash('You do not have permission to view this group.', 'danger')
        return redirect(url_for('groups_list'))

    members = group.members.all()
    is_owner = group.is_owner(current_user)
    is_member = group.is_member(current_user)
    is_admin = group.is_admin(current_user)
    invite_tokens = []
    if is_owner and group.invite_method == 'token':
        invite_tokens = GroupInviteToken.query.filter_by(group_id=group.id, used_at=None).order_by(GroupInviteToken.created_at.desc()).all()

    invite_method_label = app.config['GROUP_INVITE_METHOD_LABELS'].get(group.invite_method, group.invite_method)

    # Get all events for this group, ordered by date
    events = group.events.order_by(Event.event_date.asc()).all()
    for event in events:
        event.event_date_utc = to_utc(event.event_date)

    return render_template('groups/view.html',
                         group=group,
                         members=members,
                         is_owner=is_owner,
                         is_member=is_member,
                         is_admin=is_admin,
                         invite_tokens=invite_tokens,
                         invite_method_label=invite_method_label,
                         events=events,
                         current_time=now_utc())


@app.route('/groups/<int:group_id>/members/<int:member_id>/make-admin', methods=['POST'])
@login_required
def group_member_make_admin(group_id, member_id):
    """Promote a group member to admin"""
    group = Group.query.get_or_404(group_id)

    if not group.is_admin(current_user):
        flash('Only group admins can promote members.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    membership = GroupMember.query.get_or_404(member_id)
    if membership.group_id != group.id:
        flash('Member not found in this group.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if membership.user_id == group.owner_id:
        flash('The group owner is already an admin.', 'info')
        return redirect(url_for('group_view', group_id=group.id))

    membership.role = 'admin'
    db.session.commit()

    log_audit('group_admin_grant', f'Granted admin to user {membership.user_id} in group {group.id}', user_id=current_user.id)
    db.session.add(Notification(
        user_id=membership.user_id,
        event_id=None,
        message=f'You are now an admin of the group "{group.name}".'
    ))
    db.session.commit()

    flash('Member promoted to admin.', 'success')
    return redirect(url_for('group_view', group_id=group.id))


@app.route('/groups/<int:group_id>/members/<int:member_id>/demote', methods=['POST'])
@login_required
def group_member_demote(group_id, member_id):
    """Demote a group admin to member"""
    group = Group.query.get_or_404(group_id)

    if not group.is_owner(current_user):
        flash('Only the group owner can demote admins.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    membership = GroupMember.query.get_or_404(member_id)
    if membership.group_id != group.id:
        flash('Member not found in this group.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if membership.user_id == group.owner_id:
        flash('The group owner cannot be demoted.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    membership.role = 'member'
    db.session.commit()

    log_audit('group_admin_revoke', f'Revoked admin from user {membership.user_id} in group {group.id}', user_id=current_user.id)

    flash('Member demoted to group member.', 'success')
    return redirect(url_for('group_view', group_id=group.id))


@app.route('/groups/<int:group_id>/members/<int:member_id>/make-owner', methods=['POST'])
@login_required
def group_member_make_owner(group_id, member_id):
    """Transfer group ownership to another member"""
    group = Group.query.get_or_404(group_id)

    if not group.is_owner(current_user):
        flash('Only the group owner can transfer ownership.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    membership = GroupMember.query.get_or_404(member_id)
    if membership.group_id != group.id:
        flash('Member not found in this group.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if membership.user_id == group.owner_id:
        flash('This user is already the group owner.', 'info')
        return redirect(url_for('group_view', group_id=group.id))

    old_owner_id = group.owner_id
    group.owner_id = membership.user_id

    # Ensure new owner is an admin
    membership.role = 'admin'

    # Keep previous owner as admin member
    old_owner_membership = GroupMember.query.filter_by(group_id=group.id, user_id=old_owner_id).first()
    if old_owner_membership:
        old_owner_membership.role = 'admin'

    db.session.commit()

    log_audit('group_owner_transfer', f'Transferred ownership to user {membership.user_id} in group {group.id}', user_id=current_user.id)
    db.session.add(Notification(
        user_id=membership.user_id,
        event_id=None,
        message=f'You are now the owner of the group "{group.name}".'
    ))
    db.session.commit()

    flash('Group ownership transferred.', 'success')
    return redirect(url_for('group_view', group_id=group.id))


@app.route('/groups/<int:group_id>/members/<int:member_id>/remove', methods=['POST'])
@login_required
def group_member_remove(group_id, member_id):
    """Remove a member from a group"""
    group = Group.query.get_or_404(group_id)

    if not group.is_admin(current_user):
        flash('Only group admins can remove members.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    membership = GroupMember.query.get_or_404(member_id)
    if membership.group_id != group.id:
        flash('Member not found in this group.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if membership.user_id == group.owner_id:
        flash('The group owner cannot be removed.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    if membership.user_id == current_user.id:
        flash('You cannot remove yourself. Use Leave Group instead.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    db.session.delete(membership)
    db.session.commit()

    log_audit('group_member_remove', f'Removed user {membership.user_id} from group {group.id}', user_id=current_user.id)

    flash('Member removed from group.', 'success')
    return redirect(url_for('group_view', group_id=group.id))


@app.route('/groups/<int:group_id>/edit', methods=['GET', 'POST'])
@login_required
def group_edit(group_id):
    """Edit a group"""
    group = Group.query.get_or_404(group_id)

    # Only owner can edit
    if not group.is_owner(current_user):
        flash('Only the group owner can edit this group.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    form = create_group_form()
    if form.validate_on_submit():
        group.name = form.name.data
        group.slug = generate_unique_slug(Group, slugify(form.name.data), exclude_id=group.id)
        group.description = form.description.data
        group.group_type = form.group_type.data
        group.is_public = form.is_public.data
        group.invite_method = form.invite_method.data or app.config['GROUP_INVITE_METHOD_DEFAULT']
        db.session.commit()

        # Update tags
        remove_tags_from_object(group, GroupTag)
        if form.tags.data:
            add_tags_to_object(group, form.tags.data, GroupTag)
            db.session.commit()

        flash(f'Group "{group.name}" updated successfully!', 'success')
        return redirect(url_for('group_view', group_id=group.id))

    # Pre-populate form
    form.name.data = group.name
    form.description.data = group.description
    form.group_type.data = group.group_type
    form.is_public.data = group.is_public
    form.tags.data = ', '.join(group.get_tag_names())
    form.invite_method.data = group.invite_method
    form.submit.label.text = 'Update Group'

    return render_template('groups/edit.html', form=form, group=group)


@app.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def group_delete(group_id):
    """Delete a group"""
    group = Group.query.get_or_404(group_id)

    # Only owner can delete
    if not group.is_owner(current_user):
        flash('Only the group owner can delete this group.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    # Check if there are other members besides the owner
    other_members = group.members.filter(GroupMember.user_id != group.owner_id).count()

    if other_members > 0:
        flash(
            f'Cannot delete group "{group.name}". There are {other_members} other member(s) in this group. '
            'Please remove all members before deleting the group.',
            'warning'
        )
        return redirect(url_for('group_view', group_id=group.id))

    group_name = group.name
    db.session.delete(group)
    db.session.commit()

    log_audit('group_delete', f'Deleted group {group_id} ({group_name})', user_id=current_user.id)

    flash(f'Group "{group_name}" deleted successfully.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/groups/<int:group_id>/invite', methods=['GET', 'POST'])
@login_required
def group_invite(group_id):
    """Invite a user to a group"""
    group = Group.query.get_or_404(group_id)

    # Only owner can invite
    if not group.is_owner(current_user):
        flash('Only the group owner can invite users.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if group.invite_method == 'token':
        flash('This group only allows external invites via one-time tokens.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    form = InviteUserForm()
    if form.validate_on_submit():
        invitee = User.query.filter_by(username=form.username.data).first()

        # Check if user is already a member
        if group.is_member(invitee):
            flash(f'{invitee.username} is already a member of this group.', 'warning')
            return redirect(url_for('group_invite', group_id=group.id))

        # Check if user is the owner
        if group.is_owner(invitee):
            flash('You cannot invite yourself.', 'warning')
            return redirect(url_for('group_invite', group_id=group.id))

        # Check if invitation already exists
        existing_invitation = GroupInvitation.query.filter_by(
            group_id=group.id,
            invitee_id=invitee.id
        ).first()

        if existing_invitation:
            if existing_invitation.status == 'pending':
                flash(f'{invitee.username} already has a pending invitation.', 'warning')
            else:
                flash(f'{invitee.username} was previously invited ({existing_invitation.status}).', 'info')
            return redirect(url_for('group_invite', group_id=group.id))

        # Create invitation
        invitation = GroupInvitation(
            group_id=group.id,
            inviter_id=current_user.id,
            invitee_id=invitee.id
        )
        db.session.add(invitation)
        db.session.commit()

        flash(f'Invitation sent to {invitee.username}!', 'success')
        return redirect(url_for('group_view', group_id=group.id))

    return render_template('groups/invite.html', form=form, group=group)


@app.route('/groups/<int:group_id>/invite-token', methods=['POST'])
@login_required
def group_invite_token_generate(group_id):
    """Generate a one-time invite token for external invites"""
    group = Group.query.get_or_404(group_id)

    if not group.is_owner(current_user):
        flash('Only the group owner can generate invite tokens.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if group.invite_method != 'token':
        flash('This group is not configured for token-based invites.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    token_value = secrets.token_urlsafe(16)
    invite_token = GroupInviteToken(group_id=group.id, token=token_value)
    db.session.add(invite_token)
    db.session.commit()

    flash('New invite token generated. Share the link below with the person you want to invite.', 'success')
    return redirect(url_for('group_view', group_id=group.id))


@app.route('/groups/<int:group_id>/join/<token>', methods=['GET', 'POST'])
@login_required
def group_join_with_token(group_id, token):
    """Join a group via one-time invite token"""
    group = Group.query.get_or_404(group_id)

    if group.invite_method != 'token':
        flash('This group does not accept token-based invites.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    invite_token = GroupInviteToken.query.filter_by(group_id=group.id, token=token, used_at=None).first()
    if not invite_token:
        flash('This invite token is invalid or has already been used.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if group.is_member(current_user):
        flash('You are already a member of this group.', 'info')
        return redirect(url_for('group_view', group_id=group.id))

    membership = GroupMember(group_id=group.id, user_id=current_user.id, role='member')
    db.session.add(membership)
    invite_token.used_at = now_utc()
    invite_token.used_by_id = current_user.id
    db.session.commit()

    flash(f'You have joined the group "{group.name}" via invite token!', 'success')
    return redirect(url_for('group_view', group_id=group.id))


@app.route('/groups/<int:group_id>/leave', methods=['POST'])
@login_required
def group_leave(group_id):
    """Leave a group"""
    group = Group.query.get_or_404(group_id)

    # Check if user is a member
    membership = group.members.filter_by(user_id=current_user.id).first()
    if not membership:
        flash('You are not a member of this group.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    # Owner cannot leave their own group
    if group.is_owner(current_user):
        flash('You must transfer ownership to another member before leaving this group.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    db.session.delete(membership)
    db.session.commit()

    flash(f'You have left the group "{group.name}".', 'success')
    return redirect(url_for('dashboard'))


# Invitation Routes

@app.route('/invitations')
@login_required
def invitations_list():
    """List all invitations for the current user"""
    pending_invitations = current_user.get_pending_invitations()
    return render_template('invitations/list.html', invitations=pending_invitations)


@app.route('/invitations/<int:invitation_id>/accept', methods=['POST'])
@login_required
def invitation_accept(invitation_id):
    """Accept a group invitation"""
    invitation = GroupInvitation.query.get_or_404(invitation_id)

    # Check if invitation is for current user
    if invitation.invitee_id != current_user.id:
        flash('This invitation is not for you.', 'danger')
        return redirect(url_for('invitations_list'))

    # Check if invitation is pending
    if invitation.status != 'pending':
        flash('This invitation has already been responded to.', 'warning')
        return redirect(url_for('invitations_list'))

    try:
        invitation.accept()
        db.session.commit()
        flash(f'You have joined the group "{invitation.group.name}"!', 'success')
        return redirect(url_for('group_view', group_id=invitation.group_id))
    except IntegrityError:
        db.session.rollback()
        flash('You are already a member of this group.', 'warning')
        return redirect(url_for('invitations_list'))


@app.route('/invitations/<int:invitation_id>/reject', methods=['POST'])
@login_required
def invitation_reject(invitation_id):
    """Reject a group invitation"""
    invitation = GroupInvitation.query.get_or_404(invitation_id)

    # Check if invitation is for current user
    if invitation.invitee_id != current_user.id:
        flash('This invitation is not for you.', 'danger')
        return redirect(url_for('invitations_list'))

    # Check if invitation is pending
    if invitation.status != 'pending':
        flash('This invitation has already been responded to.', 'warning')
        return redirect(url_for('invitations_list'))

    invitation.reject()
    db.session.commit()

    flash(f'You have rejected the invitation to "{invitation.group.name}".', 'info')
    return redirect(url_for('invitations_list'))


# Event Routes

@app.route('/groups/<int:group_id>/events')
@login_required
def events_list(group_id):
    """List all events for a group"""
    group = Group.query.get_or_404(group_id)

    # Check if user can view this group
    if not group.can_view(current_user):
        flash('You do not have permission to view this group.', 'danger')
        return redirect(url_for('groups_list'))

    events = group.events.order_by(Event.event_date.desc()).all()
    for event in events:
        event.event_date_utc = to_utc(event.event_date)
    current_time_naive = now_utc()
    return render_template('events/list.html', group=group, events=events, current_time=current_time_naive)


@app.route('/groups/<int:group_id>/events/create', methods=['GET', 'POST'])
@login_required
def event_create(group_id):
    """Create a new event for a group"""
    group = Group.query.get_or_404(group_id)

    # Only members and owner can create events
    if not (group.is_owner(current_user) or group.is_member(current_user)):
        flash('You must be a member of this group to create events.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if group.is_public and not group.is_owner(current_user):
        flash('Only the group owner can create events for public groups.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    form = create_event_form()
    if form.validate_on_submit():
        # Combine date and time into a datetime object
        event_datetime = datetime.combine(form.event_date.data, form.event_time.data)

        event = Event(
            group_id=group.id,
            name=form.name.data,
            slug=generate_unique_slug(Event, slugify(form.name.data)),
            description=form.description.data,
            event_date=event_datetime,
            location_name=form.location_name.data,
            address=form.address.data,
            url=form.url.data,
            cost=form.cost.data,
            parking_difficulty=form.parking_difficulty.data if form.parking_difficulty.data else None,
            category=form.category.data if form.category.data else None,
            space=form.space.data if form.space.data else None,
            booking_requirement=form.booking_requirement.data if form.booking_requirement.data else None,
            created_by_id=current_user.id
        )
        db.session.add(event)
        db.session.commit()

        # Add tags if provided
        if form.tags.data:
            add_tags_to_object(event, form.tags.data, EventTag)
            db.session.commit()

        flash(f'Event "{event.name}" created successfully!', 'success')
        return redirect(url_for('event_view', group_id=group.id, event_id=event.id))

    return render_template('events/create.html', form=form, group=group)


@app.route('/groups/<int:group_id>/events/<int:event_id>')
def event_view(group_id, event_id):
    """View event details"""
    group = Group.query.get_or_404(group_id)
    event = Event.query.get_or_404(event_id)

    # Check if event belongs to group
    if event.group_id != group.id:
        flash('Event not found in this group.', 'danger')
        return redirect(url_for('events_list', group_id=group.id))

    # Public events are viewable by anyone; private events require membership
    if not group.is_public:
        if not current_user.is_authenticated:
            flash('Please log in to view this private group event.', 'warning')
            return redirect(url_for('login', next=request.path))
        if not group.can_view(current_user):
            flash('You do not have permission to view this group.', 'danger')
            return redirect(url_for('groups_list'))

    user_response = event.get_user_response(current_user) if current_user.is_authenticated else None
    going_users = event.get_going_users()
    interested_users = event.get_interested_users()
    not_going_users = event.get_not_going_users()

    event.event_date_utc = to_utc(event.event_date)

    return render_template('events/view.html',
                         group=group,
                         event=event,
                         user_response=user_response,
                         going_users=going_users,
                         interested_users=interested_users,
                         not_going_users=not_going_users,
                         current_time=now_utc())


@app.route('/groups/<int:group_id>/events/<int:event_id>/calendar')
def event_calendar_download(group_id, event_id):
    """Download event as an iCalendar (.ics) file"""
    group = Group.query.get_or_404(group_id)
    event = Event.query.get_or_404(event_id)

    if event.group_id != group.id:
        flash('Event not found in this group.', 'danger')
        return redirect(url_for('events_list', group_id=group.id))

    if not group.is_public:
        if not current_user.is_authenticated:
            flash('Please log in to view this private group event.', 'warning')
            return redirect(url_for('login', next=request.path))
        if not group.can_view(current_user):
            flash('You do not have permission to view this group.', 'danger')
            return redirect(url_for('groups_list'))

    event_url = url_for('event_view', group_id=group.id, event_id=event.id, _external=True)
    ics_body = build_event_ics(event, event_url)
    filename = f'groupdoo_event_{event.id}.ics'

    response = Response(ics_body, mimetype='text/calendar; charset=utf-8')
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@app.route('/groups/<int:group_id>/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def event_edit(group_id, event_id):
    """Edit an event"""
    group = Group.query.get_or_404(group_id)
    event = Event.query.get_or_404(event_id)

    # Check if event belongs to group
    if event.group_id != group.id:
        flash('Event not found in this group.', 'danger')
        return redirect(url_for('events_list', group_id=group.id))

    # Only creator or group owner can edit
    if event.created_by_id != current_user.id and not group.is_owner(current_user):
        flash('Only the event creator or group owner can edit this event.', 'danger')
        return redirect(url_for('event_view', group_id=group.id, event_id=event.id))

    if group.is_public and not group.is_owner(current_user):
        flash('Only the group owner can edit events for public groups.', 'warning')
        return redirect(url_for('event_view', group_id=group.id, event_id=event.id))

    old_event_date = event.event_date
    old_location_name = event.location_name
    old_address = event.address

    form = create_event_form()
    if form.validate_on_submit():
        # Combine date and time into a datetime object
        event_datetime = datetime.combine(form.event_date.data, form.event_time.data)

        changes = []
        if old_event_date != event_datetime:
            changes.append(
                f'Date/Time changed from {old_event_date.strftime("%B %d, %Y %I:%M %p")} to {event_datetime.strftime("%B %d, %Y %I:%M %p")}'
            )

        new_location_name = form.location_name.data
        new_address = form.address.data
        if old_location_name != new_location_name or old_address != new_address:
            old_location = f'{old_location_name}, {old_address}'
            new_location = f'{new_location_name}, {new_address}'
            changes.append(f'Location changed from {old_location} to {new_location}')

        # Update event fields
        event.name = form.name.data
        event.slug = generate_unique_slug(Event, slugify(form.name.data), exclude_id=event.id)
        event.description = form.description.data
        event.event_date = event_datetime
        event.location_name = form.location_name.data
        event.address = form.address.data
        event.url = form.url.data
        event.cost = form.cost.data
        event.parking_difficulty = form.parking_difficulty.data if form.parking_difficulty.data else None
        event.category = form.category.data if form.category.data else None
        event.space = form.space.data if form.space.data else None
        event.booking_requirement = form.booking_requirement.data if form.booking_requirement.data else None
        db.session.commit()

        # Update tags
        remove_tags_from_object(event, EventTag)
        if form.tags.data:
            add_tags_to_object(event, form.tags.data, EventTag)
            db.session.commit()

        if changes:
            message = build_event_change_message(event.name, changes)
            responses = event.responses.all()
            for response in responses:
                if response.user_id == current_user.id:
                    continue
                db.session.add(Notification(
                    user_id=response.user_id,
                    event_id=event.id,
                    message=message
                ))
            db.session.commit()

        flash(f'Event "{event.name}" updated successfully!', 'success')
        return redirect(url_for('event_view', group_id=group.id, event_id=event.id))

    # Pre-populate form
    form.name.data = event.name
    form.description.data = event.description
    form.event_date.data = event.event_date.date()
    form.event_time.data = event.event_date.time()
    form.location_name.data = event.location_name
    form.address.data = event.address
    form.url.data = event.url
    form.cost.data = event.cost
    form.parking_difficulty.data = event.parking_difficulty or ''
    form.category.data = event.category or ''
    form.space.data = event.space or ''
    form.booking_requirement.data = event.booking_requirement or ''
    form.tags.data = ', '.join(event.get_tag_names())
    form.submit.label.text = 'Update Event'

    return render_template('events/edit.html', form=form, group=group, event=event)


@app.route('/groups/<int:group_id>/events/<int:event_id>/delete', methods=['POST'])
@login_required
def event_delete(group_id, event_id):
    """Delete an event"""
    group = Group.query.get_or_404(group_id)
    event = Event.query.get_or_404(event_id)

    # Check if event belongs to group
    if event.group_id != group.id:
        flash('Event not found in this group.', 'danger')
        return redirect(url_for('events_list', group_id=group.id))

    # Only creator or group owner can delete
    if event.created_by_id != current_user.id and not group.is_owner(current_user):
        flash('Only the event creator or group owner can delete this event.', 'danger')
        return redirect(url_for('event_view', group_id=group.id, event_id=event.id))

    # Check if there are responses to this event
    response_count = event.responses.count()

    if response_count > 0:
        flash(
            f'Cannot delete event "{event.name}". {response_count} member(s) have responded to this event. '
            'Please remove all responses before deleting the event.',
            'warning'
        )
        return redirect(url_for('event_view', group_id=group.id, event_id=event.id))

    event_name = event.name
    db.session.delete(event)
    db.session.commit()

    log_audit('event_delete', f'Deleted event {event_id} ({event_name}) in group {group_id}', user_id=current_user.id)

    flash(f'Event "{event_name}" deleted successfully.', 'success')
    return redirect(url_for('events_list', group_id=group.id))


@app.route('/groups/<int:group_id>/events/<int:event_id>/respond/<status>', methods=['POST'])
@login_required
def event_respond(group_id, event_id, status):
    """Respond to an event (going, interested, not_going)"""
    if status not in ['going', 'interested', 'not_going']:
        flash('Invalid response status.', 'danger')
        return redirect(url_for('groups_list'))

    group = Group.query.get_or_404(group_id)
    event = Event.query.get_or_404(event_id)

    # Check if event belongs to group
    if event.group_id != group.id:
        flash('Event not found in this group.', 'danger')
        return redirect(url_for('events_list', group_id=group.id))

    # Check if user is a member of the group
    if not (group.is_owner(current_user) or group.is_member(current_user)):
        flash('You must be a member of this group to respond to events.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    # Check if user already responded
    existing_response = event.get_user_response(current_user)

    if existing_response:
        # Update existing response
        existing_response.status = status
        existing_response.responded_at = utcnow()
    else:
        # Create new response
        response = EventResponse(
            event_id=event.id,
            user_id=current_user.id,
            status=status
        )
        db.session.add(response)

    db.session.commit()

    status_text = {
        'going': 'going',
        'interested': 'interested',
        'not_going': 'not going'
    }
    flash(f'You are now marked as {status_text[status]} for this event.', 'success')
    return redirect(url_for('event_view', group_id=group.id, event_id=event.id))


@app.cli.command()
def init_db():
    """Initialize the database"""
    db.create_all()
    print('Database tables created.')


@app.route('/groups/join-token', methods=['POST'])
@login_required
def group_join_from_dashboard():
    """Join a group by pasting a one-time invite token link or token"""
    raw_value = (request.form.get('invite_token') or '').strip()

    if not raw_value:
        flash('Please paste an invite link or token.', 'warning')
        return redirect(url_for('dashboard'))

    # Accept a full invite link or just the token
    match = re.search(r'/groups/(\d+)/join/([^/\s]+)', raw_value)
    if match:
        group_id = int(match.group(1))
        token = match.group(2)
    else:
        token = raw_value
        invite_token = GroupInviteToken.query.filter_by(token=token, used_at=None).first()
        if not invite_token:
            flash('This invite token is invalid or has already been used.', 'danger')
            return redirect(url_for('dashboard'))
        group_id = invite_token.group_id

    return redirect(url_for('group_join_with_token', group_id=group_id, token=token))


@app.route('/account/delete', methods=['GET', 'POST'])
@login_required
@limiter.limit("2 per hour")
def account_delete():
    """Delete the current user's account after confirmation"""
    form = AccountDeleteForm()
    if form.validate_on_submit():
        if form.confirm_username.data != current_user.username:
            flash('Username does not match. Account not deleted.', 'danger')
            return redirect(url_for('account_delete'))

        user_id = current_user.id
        log_audit('account_delete', f'Account deletion requested for {current_user.username}', user_id=user_id)

        # Delete user-created events to avoid FK constraints
        for event in Event.query.filter_by(created_by_id=user_id).all():
            db.session.delete(event)

        # Clear user-specific relationships
        EventResponse.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        GroupInvitation.query.filter(
            or_(GroupInvitation.inviter_id == user_id, GroupInvitation.invitee_id == user_id)
        ).delete(synchronize_session=False)
        GroupMember.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        Notification.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        GroupInviteToken.query.filter_by(used_by_id=user_id).update(
            {GroupInviteToken.used_by_id: None},
            synchronize_session=False
        )

        # Transfer or delete owned groups
        owned_groups = Group.query.filter_by(owner_id=user_id).all()
        for group in owned_groups:
            other_members = GroupMember.query.filter(
                GroupMember.group_id == group.id,
                GroupMember.user_id != user_id
            ).order_by(GroupMember.joined_at.asc()).all()

            if not other_members:
                GroupInviteToken.query.filter_by(group_id=group.id).delete(synchronize_session=False)
                db.session.delete(group)
                continue

            new_owner_member = other_members[0]
            group.owner_id = new_owner_member.user_id
            new_owner_member.role = 'admin'
            log_audit('group_owner_transfer', f'Transferred ownership to user {new_owner_member.user_id} in group {group.id}', user_id=user_id)
            db.session.add(Notification(
                user_id=new_owner_member.user_id,
                event_id=None,
                message=f'You are now the owner of the group "{group.name}".'
            ))

        # Delete user
        user = db.session.get(User, user_id)
        if user:
            db.session.delete(user)

        db.session.commit()
        logout_user()
        flash('Your account has been deleted.', 'info')
        return redirect(url_for('index'))

    return render_template('account/delete.html', form=form)


def slugify(value):
    """Create a URL-safe slug from a string"""
    value = (value or '').lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value or 'item'


def generate_unique_slug(model, base_slug, exclude_id=None):
    """Generate a unique slug for the given model"""
    slug = base_slug
    counter = 2
    while True:
        query = model.query.filter_by(slug=slug)
        if exclude_id is not None:
            query = query.filter(model.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


# ============================================================================
# GDPR ROUTES
# ============================================================================

@app.route('/gdpr/banner-check', methods=['GET'])
def gdpr_banner_check():
    """Check if user has accepted GDPR banner - works for both authenticated and guest users"""
    from models import GDPRConsent

    if current_user.is_authenticated:
        # Check user's database consent
        banner_consent = GDPRConsent.query.filter_by(
            user_id=current_user.id,
            consent_type='banner',
            consented=True
        ).first()
        return {
            'accepted': banner_consent is not None,
            'type': 'user'
        }
    else:
        # For guests, return info that we'll check localStorage
        return {
            'accepted': False,
            'type': 'guest'
        }


@app.route('/gdpr/banner-accept', methods=['POST'])
@login_required
def gdpr_banner_accept():
    """Accept GDPR banner consent - sets banner_consent flag for user"""
    from models import GDPRConsent

    # Check if banner consent already exists
    banner_consent = GDPRConsent.query.filter_by(
        user_id=current_user.id,
        consent_type='banner'
    ).first()

    if not banner_consent:
        # Create new banner consent record
        banner_consent = GDPRConsent(
            user_id=current_user.id,
            consent_type='banner',
            consented=True,
            consented_at=now_utc(),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255]
        )
        db.session.add(banner_consent)
    else:
        # Update existing consent
        banner_consent.consented = True
        banner_consent.consented_at = now_utc()
        banner_consent.ip_address = request.remote_addr

    db.session.commit()
    log_audit('banner_consent_accepted', 'User accepted GDPR banner', user_id=current_user.id)

    return {'status': 'success', 'message': 'Consent recorded'}, 200


@app.route('/gdpr/privacy')
def gdpr_privacy():
    """Privacy policy and GDPR information page"""
    return render_template('gdpr/privacy.html')


@app.route('/gdpr/consent', methods=['GET', 'POST'])
@login_required
def gdpr_consent():
    """Manage user consent preferences"""
    from models import GDPRConsent

    if request.method == 'POST':
        for consent_type in app.config['GDPR_CONSENT_TYPES']:
            value = request.form.get(f'consent_{consent_type}') == 'on'
            consent = GDPRConsent.query.filter_by(user_id=current_user.id, consent_type=consent_type).first()

            if consent:
                consent.consented = value
                if value:
                    consent.consented_at = now_utc()
            else:
                consent = GDPRConsent(
                    user_id=current_user.id,
                    consent_type=consent_type,
                    consented=value,
                    consented_at=now_utc() if value else None,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')[:255]
                )
                db.session.add(consent)

        db.session.commit()
        log_audit('consent_updated', f'GDPR consent preferences updated', user_id=current_user.id)
        flash('Your consent preferences have been updated.', 'success')
        return redirect(url_for('gdpr_consent'))

    # Get current consent preferences
    user_consents = {c.consent_type: c.consented for c in current_user.gdpr_consents}
    consent_types = app.config['GDPR_CONSENT_TYPES']

    return render_template('gdpr/consent.html', consents=user_consents, consent_types=consent_types)


@app.route('/gdpr/export', methods=['GET', 'POST'])
@login_required
def gdpr_export():
    """Request personal data export (GDPR Article 20)"""
    from models import GDPRDataExport
    from datetime import timedelta
    import json
    import io

    if request.method == 'POST':
        # Rate limiting
        recent_exports = GDPRDataExport.query.filter_by(user_id=current_user.id).filter(
            GDPRDataExport.requested_at > now_utc() - timedelta(days=1)
        ).count()

        if recent_exports >= app.config['GDPR_MAX_DATA_EXPORT_REQUESTS_PER_DAY']:
            flash(f'You can only request {app.config["GDPR_MAX_DATA_EXPORT_REQUESTS_PER_DAY"]} data exports per day. Please try again tomorrow.', 'warning')
            return redirect(url_for('gdpr_export'))

        export_format = request.form.get('format', 'json')
        if export_format not in ['json', 'csv']:
            flash('Invalid export format.', 'danger')
            return redirect(url_for('gdpr_export'))

        # Create export request
        download_token = secrets.token_urlsafe(32)
        export_request = GDPRDataExport(
            user_id=current_user.id,
            export_format=export_format,
            download_token=download_token,
            download_token_expires_at=now_utc() + timedelta(hours=app.config['GDPR_DOWNLOAD_TOKEN_EXPIRY_HOURS']),
            expires_at=now_utc() + timedelta(days=app.config['GDPR_DATA_EXPORT_EXPIRY_DAYS']),
            ip_address=request.remote_addr
        )
        db.session.add(export_request)
        db.session.commit()

        log_audit('data_export_requested', f'GDPR data export requested (format: {export_format})', user_id=current_user.id)
        flash('Your data export request has been submitted. Your data will be available for download shortly.', 'success')
        return redirect(url_for('gdpr_export'))

    # Get user's export requests
    exports = GDPRDataExport.query.filter_by(user_id=current_user.id).order_by(GDPRDataExport.requested_at.desc()).all()
    return render_template('gdpr/export.html', exports=exports)


@app.route('/gdpr/export/<token>/download')
@login_required
def gdpr_export_download(token):
    """Download exported personal data"""
    from models import GDPRDataExport
    import json

    export = GDPRDataExport.query.filter_by(download_token=token, user_id=current_user.id).first_or_404()

    # Check if token has expired
    if export.download_token_expires_at < now_utc():
        flash('Download link has expired. Please request a new export.', 'danger')
        return redirect(url_for('gdpr_export'))

    if export.status != 'completed':
        flash('Your export is not ready for download yet. Please check back soon.', 'warning')
        return redirect(url_for('gdpr_export'))

    # Build data export
    user_data = {
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
        },
        'groups_owned': [],
        'groups_member_of': [],
        'events_created': [],
        'event_responses': [],
        'invitations_sent': [],
        'invitations_received': [],
        'audit_logs': []
    }

    # Groups owned
    for group in current_user.owned_groups:
        user_data['groups_owned'].append({
            'id': group.id,
            'name': group.name,
            'created_at': group.created_at.isoformat() if group.created_at else None
        })

    # Groups member of
    for membership in current_user.group_memberships:
        user_data['groups_member_of'].append({
            'id': membership.group.id,
            'name': membership.group.name,
            'role': membership.role,
            'joined_at': membership.joined_at.isoformat() if membership.joined_at else None
        })

    # Events created
    for event in current_user.created_events:
        user_data['events_created'].append({
            'id': event.id,
            'name': event.name,
            'event_date': event.event_date.isoformat() if event.event_date else None,
            'created_at': event.created_at.isoformat() if event.created_at else None
        })

    # Event responses
    for response in current_user.event_responses:
        user_data['event_responses'].append({
            'event_id': response.event_id,
            'event_name': response.event.name,
            'status': response.status,
            'responded_at': response.responded_at.isoformat() if response.responded_at else None
        })

    # Invitations
    for invite in current_user.sent_invitations:
        user_data['invitations_sent'].append({
            'group': invite.group.name,
            'invitee': invite.invitee.username,
            'status': invite.status,
            'created_at': invite.created_at.isoformat() if invite.created_at else None
        })

    for invite in current_user.received_invitations:
        user_data['invitations_received'].append({
            'group': invite.group.name,
            'inviter': invite.inviter.username,
            'status': invite.status,
            'created_at': invite.created_at.isoformat() if invite.created_at else None
        })

    # Audit logs
    for log in current_user.audit_logs:
        user_data['audit_logs'].append({
            'event_type': log.event_type,
            'message': log.message,
            'ip_address': log.ip_address,
            'created_at': log.created_at.isoformat() if log.created_at else None
        })

    # Generate file
    json_data = json.dumps(user_data, indent=2, default=str)

    log_audit('data_export_downloaded', f'GDPR data export downloaded', user_id=current_user.id)

    from flask import send_file
    return send_file(
        io.BytesIO(json_data.encode()),
        mimetype='application/json',
        as_attachment=True,
        download_name=f'groupdoo_data_export_{current_user.id}_{now_utc().strftime("%Y%m%d")}.json'
    )


@app.route('/gdpr/delete', methods=['GET', 'POST'])
@login_required
def gdpr_delete_request():
    """Request account deletion (GDPR Right to be forgotten - Article 17)"""
    from models import GDPRDeletionRequest

    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()

        # Check for existing pending deletion request
        existing = GDPRDeletionRequest.query.filter(
            GDPRDeletionRequest.user_id == current_user.id,
            GDPRDeletionRequest.status.in_(['pending', 'confirmed'])
        ).first()

        if existing:
            flash('You already have a pending deletion request. Please wait for confirmation or cancel it first.', 'warning')
            return redirect(url_for('gdpr_delete_request'))

        # Create deletion request
        confirmation_token = secrets.token_urlsafe(32)
        deletion_request = GDPRDeletionRequest(
            user_id=current_user.id,
            confirmation_token=confirmation_token,
            confirmation_token_expires_at=now_utc() + timedelta(hours=app.config['GDPR_DELETION_CONFIRMATION_HOURS']),
            reason=reason,
            ip_address=request.remote_addr
        )
        db.session.add(deletion_request)
        db.session.commit()

        log_audit('deletion_requested', f'GDPR account deletion requested', user_id=current_user.id)
        flash('Account deletion request submitted. You will receive a confirmation email. Click the link in the email to confirm deletion.', 'info')

        # TODO: Send confirmation email with deletion_request.confirmation_token

        return redirect(url_for('gdpr_delete_request'))

    # Get deletion requests
    deletion_requests = GDPRDeletionRequest.query.filter_by(user_id=current_user.id).order_by(GDPRDeletionRequest.requested_at.desc()).all()
    return render_template('gdpr/delete_request.html', deletion_requests=deletion_requests)


@app.route('/gdpr/delete/<token>/confirm', methods=['GET', 'POST'])
def gdpr_delete_confirm(token):
    """Confirm account deletion"""
    from models import GDPRDeletionRequest

    deletion_request = GDPRDeletionRequest.query.filter_by(confirmation_token=token).first_or_404()

    # Check if token expired
    if deletion_request.confirmation_token_expires_at < now_utc():
        deletion_request.status = 'cancelled'
        db.session.commit()
        flash('Confirmation link has expired. Please submit a new deletion request.', 'danger')
        return redirect(url_for('index'))

    if deletion_request.status != 'pending':
        flash('This deletion request is no longer valid.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Confirm the deletion
        deletion_request.status = 'confirmed'
        deletion_request.confirmed_at = now_utc()
        db.session.commit()

        user_id = deletion_request.user_id
        log_audit('deletion_confirmed', f'GDPR account deletion confirmed', user_id=user_id)

        # Schedule actual deletion (30 days grace period)
        # TODO: Add Celery task or scheduled job to delete account after grace period

        flash('Your account deletion has been confirmed. Your account will be permanently deleted in 30 days.', 'info')
        return redirect(url_for('index'))

    return render_template('gdpr/delete_confirm.html', deletion_request=deletion_request)


@app.route('/gdpr/delete/<token>/cancel', methods=['POST'])
@login_required
def gdpr_delete_cancel(token):
    """Cancel account deletion request"""
    from models import GDPRDeletionRequest

    deletion_request = GDPRDeletionRequest.query.filter_by(confirmation_token=token, user_id=current_user.id).first_or_404()

    if deletion_request.status not in ['pending', 'confirmed']:
        flash('This deletion request cannot be cancelled.', 'warning')
        return redirect(url_for('gdpr_delete_request'))

    deletion_request.status = 'cancelled'
    db.session.commit()

    log_audit('deletion_cancelled', f'GDPR account deletion request cancelled', user_id=current_user.id)
    flash('Your account deletion request has been cancelled.', 'info')
    return redirect(url_for('gdpr_delete_request'))


@app.route('/groups/<int:group_id>/events/<int:event_id>/duplicate', methods=['GET'])
@login_required
def event_duplicate(group_id, event_id):
    """Duplicate an event by pre-filling the create form"""
    group = Group.query.get_or_404(group_id)
    event = Event.query.get_or_404(event_id)

    if event.group_id != group.id:
        flash('Event not found in this group.', 'danger')
        return redirect(url_for('events_list', group_id=group.id))

    # Only members and owner can create events
    if not (group.is_owner(current_user) or group.is_member(current_user)):
        flash('You must be a member of this group to create events.', 'danger')
        return redirect(url_for('group_view', group_id=group.id))

    if group.is_public and not group.is_owner(current_user):
        flash('Only the group owner can create events for public groups.', 'warning')
        return redirect(url_for('group_view', group_id=group.id))

    form = create_event_form()
    form.name.data = event.name
    form.description.data = event.description
    form.event_date.data = event.event_date.date()
    form.event_time.data = event.event_date.time()
    form.location_name.data = event.location_name
    form.address.data = event.address
    form.url.data = event.url
    form.cost.data = event.cost
    form.parking_difficulty.data = event.parking_difficulty or ''
    form.category.data = event.category or ''
    form.space.data = event.space or ''
    form.booking_requirement.data = event.booking_requirement or ''
    form.tags.data = ', '.join(event.get_tag_names())

    return render_template('events/create.html', form=form, group=group)


@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for crawlers"""
    content = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Sitemap: " + url_for('sitemap_xml', _external=True)
    ])
    return Response(content, mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap_xml():
    """Generate a simple sitemap for public pages"""
    base_url = app.config.get('SITE_URL') or request.url_root.rstrip('/')

    urls = [
        url_for('index', _external=True),
        url_for('search', _external=True),
        url_for('gdpr_privacy', _external=True)
    ]

    public_groups = Group.query.filter_by(is_public=True).all()
    for group in public_groups:
        urls.append(url_for('group_view', group_id=group.id, _external=True))
        for event in group.events.all():
            urls.append(url_for('event_view', group_id=group.id, event_id=event.id, _external=True))

    xml_items = []
    for link in sorted(set(urls)):
        xml_items.append(
            f"<url><loc>{link}</loc></url>"
        )

    xml_body = "\n".join(xml_items)
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
""".format(body=xml_body)

    return Response(xml, mimetype='application/xml')


if __name__ == '__main__':
    app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])
