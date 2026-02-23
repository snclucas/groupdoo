from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, TimeField, DecimalField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, URL, Optional, NumberRange
from wtforms.fields import DateField
from models import User
import re


def validate_strong_password(form, field):
    """Require strong passwords with mixed character types"""
    password = field.data or ''
    if len(password) < 8:
        raise ValidationError('Password must be at least 8 characters long')
    if not re.search(r'[A-Z]', password):
        raise ValidationError('Password must include an uppercase letter')
    if not re.search(r'[a-z]', password):
        raise ValidationError('Password must include a lowercase letter')
    if not re.search(r'\d', password):
        raise ValidationError('Password must include a number')
    if not re.search(r'[^A-Za-z0-9]', password):
        raise ValidationError('Password must include a symbol')


class LoginForm(FlaskForm):
    """Form for user login"""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class PasswordResetRequestForm(FlaskForm):
    """Form for requesting a password reset"""
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Invalid email address')
    ])
    submit = SubmitField('Send Reset Link')


class PasswordResetForm(FlaskForm):
    """Form for confirming a password reset"""
    password = PasswordField('New Password', validators=[
        DataRequired(),
        validate_strong_password
    ])
    password2 = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')


class RegistrationForm(FlaskForm):
    """Form for user registration"""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        validate_strong_password
    ])
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

    def validate_username(self, username):
        """Check if username is already taken"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')

    def validate_email(self, email):
        """Check if email is already registered"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')


class ProfileUpdateForm(FlaskForm):
    """Form for updating account profile details"""
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Invalid email address')
    ])
    language = SelectField('Language', validators=[DataRequired()])
    submit = SubmitField('Save Changes')


class PasswordChangeForm(FlaskForm):
    """Form for changing the current user's password"""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        validate_strong_password
    ])
    new_password2 = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')


class GroupForm(FlaskForm):
    """Form for creating and editing groups"""
    name = StringField('Group Name', validators=[
        DataRequired(),
        Length(min=3, max=100, message='Group name must be between 3 and 100 characters')
    ])
    description = TextAreaField('Description', validators=[
        Length(max=500, message='Description must be less than 500 characters')
    ])
    group_type = SelectField('Group Type', validators=[DataRequired()], choices=[
        ('meetup', 'Meetup'),
        ('online', 'Online'),
        ('playdate', 'Playdate')
    ])
    is_public = BooleanField('Public Group', default=True)
    tags = StringField('Tags', validators=[
        Length(max=500, message='Tags must be less than 500 characters')
    ])
    invite_method = SelectField('Invite Method', validators=[Optional()])
    submit = SubmitField('Create Group')


class InviteUserForm(FlaskForm):
    """Form for inviting users to a group"""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80)
    ])
    submit = SubmitField('Send Invitation')

    def validate_username(self, username):
        """Check if username exists"""
        user = User.query.filter_by(username=username.data).first()
        if not user:
            raise ValidationError('User not found. Please check the username.')


class EventForm(FlaskForm):
    """Form for creating and editing events"""
    name = StringField('Event Name', validators=[
        DataRequired(),
        Length(min=3, max=150, message='Event name must be between 3 and 150 characters')
    ])
    description = TextAreaField('Description', validators=[
        Length(max=1000, message='Description must be less than 1000 characters')
    ])
    event_date = DateField('Event Date', format='%Y-%m-%d', validators=[DataRequired()])
    event_time = TimeField('Event Time', format='%H:%M', validators=[DataRequired()])
    location_name = StringField('Location Name', validators=[
        DataRequired(),
        Length(min=3, max=150, message='Location name must be between 3 and 150 characters')
    ])
    address = StringField('Address', validators=[
        DataRequired(),
        Length(min=5, max=255, message='Address must be between 5 and 255 characters')
    ])
    url = StringField('Event URL', validators=[
        Optional(),
        URL(message='Please enter a valid URL'),
        Length(max=500, message='URL must be less than 500 characters')
    ])
    cost = DecimalField('Cost (Approximate)', places=2, validators=[
        Optional(),
        NumberRange(min=0, message='Cost must be a positive number')
    ])
    parking_difficulty = SelectField('Parking Availability', validators=[Optional()], choices=[
        ('', 'Don\'t show parking info'),
        ('Good', 'Good'),
        ('Mostly good', 'Mostly good'),
        ('Limited', 'Limited'),
        ('Very limited', 'Very limited')
    ])
    category = SelectField('Category', validators=[Optional()])  # Choices will be set dynamically from config
    space = SelectField('Space', validators=[Optional()])  # Choices will be set dynamically from config
    booking_requirement = SelectField('Booking Requirement', validators=[Optional()], choices=[
        ('', 'Don\'t show booking info'),
        ('Requires booking', 'Requires booking'),
        ('No booking required', 'No booking required')
    ])
    tags = StringField('Tags', validators=[
        Length(max=500, message='Tags must be less than 500 characters')
    ])
    submit = SubmitField('Create Event')


class AccountDeleteForm(FlaskForm):
    """Form to confirm account deletion"""
    confirm_username = StringField('Confirm Username', validators=[
        DataRequired(),
        Length(min=3, max=80)
    ])
    submit = SubmitField('Delete Account')
