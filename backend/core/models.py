from django.db import models

# NOTE: tokens are stored as plain text here because this is a local demo.
# Before this went anywhere real they would be encrypted at rest - see
# docs/10-security-notes.md.


class GoogleCredential(models.Model):
    """
    The tokens Google gave us.

    This demo serves one person, so there is only ever one row, at pk=1.
    Supporting many users means adding a user foreign key here and
    filtering every lookup by the logged-in user.
    """

    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)


class SlackInstallation(models.Model):
    """The bot token for the workspace our app was installed into."""

    bot_token = models.TextField()
    team_id = models.CharField(max_length=64)
    team_name = models.CharField(max_length=255)
    updated_at = models.DateTimeField(auto_now=True)
