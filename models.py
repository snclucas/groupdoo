from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timezone

db = SQLAlchemy()


def utcnow():
    """Timezone-aware UTC now for database defaults"""
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    owned_groups = db.relationship('Group', backref='owner', lazy='dynamic', foreign_keys='Group.owner_id')
    group_memberships = db.relationship('GroupMember', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    sent_invitations = db.relationship('GroupInvitation', backref='inviter', lazy='dynamic',
                                      foreign_keys='GroupInvitation.inviter_id')
    received_invitations = db.relationship('GroupInvitation', backref='invitee', lazy='dynamic',
                                          foreign_keys='GroupInvitation.invitee_id')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and set the user's password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if the provided password matches the hash"""
        return check_password_hash(self.password_hash, password)

    def get_pending_invitations(self):
        """Get pending invitations for this user"""
        return self.received_invitations.filter_by(status='pending').all()

    def get_pending_invitation_count(self):
        """Get count of pending invitations"""
        return self.received_invitations.filter_by(status='pending').count()

    def __repr__(self):
        return f'<User {self.username}>'


class Group(db.Model):
    """Group model for user groups"""
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    group_type = db.Column(db.String(20), nullable=False)  # meetup, online, playdate
    is_public = db.Column(db.Boolean, default=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invite_method = db.Column(db.String(20), nullable=False, default='website')
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    members = db.relationship('GroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    invitations = db.relationship('GroupInvitation', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    events = db.relationship('Event', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    tags = db.relationship('GroupTag', backref='group', lazy='dynamic', cascade='all, delete-orphan')

    def is_owner(self, user):
        """Check if user is the owner of this group"""
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        return self.owner_id == user.id

    def is_member(self, user):
        """Check if user is a member of this group"""
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        return self.members.filter_by(user_id=user.id).first() is not None

    def is_admin(self, user):
        """Check if user is an admin of this group"""
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        if self.is_owner(user):
            return True
        membership = self.members.filter_by(user_id=user.id).first()
        return membership is not None and membership.role == 'admin'

    def get_member_count(self):
        """Get count of members in this group"""
        return self.members.count()

    def can_view(self, user):
        """Check if user can view this group"""
        return self.is_public or self.is_owner(user) or self.is_member(user)

    def get_tag_names(self):
        """Get list of tag names for this group"""
        return [gt.tag.name for gt in self.tags.all()]

    def invite(self, user):
        """Invite a user to the group"""
        invitation = GroupInvitation(group_id=self.id, invitee_id=user.id, inviter_id=self.owner_id)
        db.session.add(invitation)
        db.session.commit()

    def __repr__(self):
        return f'<Group {self.name}>'


class Event(db.Model):
    """Event model for group events"""
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False, index=True)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    event_date = db.Column(db.DateTime, nullable=False)
    location_name = db.Column(db.String(150), nullable=False)  # e.g., "Kids Play Zone"
    address = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=True)  # Optional URL for the event
    cost = db.Column(db.Numeric(10, 2), nullable=True)  # Optional cost/price for the event
    parking_difficulty = db.Column(db.String(20), nullable=True)  # Parking: 'Good', 'Mostly good', 'Limited', 'Very limited', or None
    category = db.Column(db.String(50), nullable=True)  # Event category: 'Playdate', 'Meal', 'Museum visit', 'Other', or None for uncategorised
    space = db.Column(db.String(20), nullable=True)  # Event space: 'Indoor', 'Outdoor', 'Both', or None for not specified
    booking_requirement = db.Column(db.String(30), nullable=True)  # 'Requires booking', 'No booking required', or None
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    responses = db.relationship('EventResponse', backref='event', lazy='dynamic', cascade='all, delete-orphan')
    created_by = db.relationship('User', backref='created_events')
    tags = db.relationship('EventTag', backref='event', lazy='dynamic', cascade='all, delete-orphan')

    def get_going_users(self):
        """Get list of users going to event"""
        return self.responses.filter_by(status='going').all()

    def get_interested_users(self):
        """Get list of users interested in event"""
        return self.responses.filter_by(status='interested').all()

    def get_not_going_users(self):
        """Get list of users not going"""
        return self.responses.filter_by(status='not_going').all()

    def get_no_response_users(self):
        """Get list of users who haven't responded"""
        responded_user_ids = [r.user_id for r in self.responses.all()]
        group_member_ids = [m.user_id for m in self.group.members.all()]
        return [m for m in group_member_ids if m not in responded_user_ids]

    def get_user_response(self, user):
        """Get a user's response to this event"""
        return self.responses.filter_by(user_id=user.id).first()

    def get_tag_names(self):
        """Get list of tag names for this event"""
        return [et.tag.name for et in self.tags.all()]

    def __repr__(self):
        return f'<Event {self.name}>'


class EventResponse(db.Model):
    """User response to event (RSVP)"""
    __tablename__ = 'event_responses'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # going, interested, not_going
    responded_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Relationships
    user = db.relationship('User', backref='event_responses')

    # Composite unique constraint to prevent duplicate responses
    __table_args__ = (db.UniqueConstraint('event_id', 'user_id', name='unique_event_response'),)

    def __repr__(self):
        return f'<EventResponse event_id={self.event_id} user_id={self.user_id} status={self.status}>'


class GroupMember(db.Model):
    """Group membership model"""
    __tablename__ = 'group_members'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='member')
    joined_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Composite unique constraint to prevent duplicate memberships
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='unique_group_member'),)

    def __repr__(self):
        return f'<GroupMember group_id={self.group_id} user_id={self.user_id} role={self.role}>'


class GroupInvitation(db.Model):
    """Group invitation model"""
    __tablename__ = 'group_invitations'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    inviter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invitee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, accepted, rejected
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    responded_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Composite unique constraint to prevent duplicate invitations
    __table_args__ = (db.UniqueConstraint('group_id', 'invitee_id', name='unique_group_invitation'),)

    def accept(self):
        """Accept the invitation"""
        self.status = 'accepted'
        self.responded_at = utcnow()
        # Add user to group
        membership = GroupMember(group_id=self.group_id, user_id=self.invitee_id, role='member')
        db.session.add(membership)

    def reject(self):
        """Reject the invitation"""
        self.status = 'rejected'
        self.responded_at = utcnow()

    def __repr__(self):
        return f'<GroupInvitation group_id={self.group_id} invitee_id={self.invitee_id} status={self.status}>'


class Tag(db.Model):
    """Tag model for labeling groups and events"""
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    color = db.Column(db.String(7), default='#007bff')  # Hex color code
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Relationships
    group_tags = db.relationship('GroupTag', backref='tag', lazy='dynamic', cascade='all, delete-orphan')
    event_tags = db.relationship('EventTag', backref='tag', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Tag {self.name}>'


class GroupTag(db.Model):
    """Association table for Group-Tag relationship"""
    __tablename__ = 'group_tags'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Composite unique constraint to prevent duplicate tags
    __table_args__ = (db.UniqueConstraint('group_id', 'tag_id', name='unique_group_tag'),)

    def __repr__(self):
        return f'<GroupTag group_id={self.group_id} tag_id={self.tag_id}>'


class EventTag(db.Model):
    """Association table for Event-Tag relationship"""
    __tablename__ = 'event_tags'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    # Composite unique constraint to prevent duplicate tags
    __table_args__ = (db.UniqueConstraint('event_id', 'tag_id', name='unique_event_tag'),)

    def __repr__(self):
        return f'<EventTag event_id={self.event_id} tag_id={self.tag_id}>'


class GroupInviteToken(db.Model):
    """One-time invite token for external invites"""
    __tablename__ = 'group_invite_tokens'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    used_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    group = db.relationship('Group', backref='invite_tokens')
    used_by = db.relationship('User', backref='used_invite_tokens')

    def __repr__(self):
        return f'<GroupInviteToken group_id={self.group_id} token={self.token} used_at={self.used_at}>'


class Notification(db.Model):
    """In-app notification for user updates"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    event = db.relationship('Event', backref='notifications')

    def __repr__(self):
        return f'<Notification user_id={self.user_id} event_id={self.event_id} read={self.is_read}>'


class AuditLog(db.Model):
    """Audit log for security-relevant actions"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)

    user = db.relationship('User', backref='audit_logs')

    def __repr__(self):
        return f'<AuditLog event_type={self.event_type} user_id={self.user_id}>'


class GDPRConsent(db.Model):
    """GDPR Consent tracking for user privacy preferences"""
    __tablename__ = 'gdpr_consents'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    consent_type = db.Column(db.String(50), nullable=False)  # e.g., 'marketing', 'analytics', 'third_party'
    consented = db.Column(db.Boolean, default=False, nullable=False)
    consented_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = db.relationship('User', backref='gdpr_consents')
    __table_args__ = (db.UniqueConstraint('user_id', 'consent_type', name='unique_user_consent_type'),)

    def __repr__(self):
        return f'<GDPRConsent user_id={self.user_id} type={self.consent_type} consented={self.consented}>'


class GDPRDataExport(db.Model):
    """GDPR Data export requests and archive records"""
    __tablename__ = 'gdpr_data_exports'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, completed, failed, expired
    export_format = db.Column(db.String(20), nullable=False, default='json')  # json, csv
    download_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    download_token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)  # bytes
    requested_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)  # Data is deleted after expiry
    ip_address = db.Column(db.String(64), nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref='gdpr_data_exports')

    def __repr__(self):
        return f'<GDPRDataExport user_id={self.user_id} status={self.status}>'


class GDPRDeletionRequest(db.Model):
    """GDPR Right to be forgotten (deletion) requests"""
    __tablename__ = 'gdpr_deletion_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, confirmed, completed, cancelled
    confirmation_token = db.Column(db.String(64), unique=True, nullable=True, index=True)
    confirmation_token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    requested_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    reason = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)

    user = db.relationship('User', backref='gdpr_deletion_requests')

    def __repr__(self):
        return f'<GDPRDeletionRequest user_id={self.user_id} status={self.status}>'
