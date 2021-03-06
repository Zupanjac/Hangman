#!/usr/bin/env python

"""main.py - This file contains handlers that are called by taskqueue and/or
cronjobs."""

import webapp2
from google.appengine.api import mail, app_identity
from google.appengine.ext import ndb
from api import GuessANumberApi

from models import User, Game


class SendReminderEmail(webapp2.RequestHandler):
    def get(self):
        """Send a reminder email to each User with an email about games.
        Called every hour using a cron job"""
        app_id = app_identity.get_application_id()
        users = User.query(User.email != None)
        for user in users:
            ancestor_key = ndb.Key(User, user.name)
            game_count = Game.query(ancestor=ancestor_key).filter(
                        Game.game_over == False, Game.canceled == False).count()
            if game_count > 0:
                subject = 'Active games'
                body = 'Hello {}, dont forget you still have active games!'.format(user.name)
                # This will send test emails, the arguments to send_mail are:
                # from, to, subject, body
                mail.send_mail('noreply@{}.appspotmail.com'.format(app_id),
                                user.email,
                                subject,
                                body)


class UpdateAverageMovesRemaining(webapp2.RequestHandler):
    def post(self):
        """Update game listing announcement in memcache."""
        # GuessANumberApi._cache_average_attempts()
        self.response.set_status(204)


app = webapp2.WSGIApplication([
    ('/crons/send_reminder', SendReminderEmail)
  #  ('/tasks/cache_average_attempts', UpdateAverageMovesRemaining),
], debug=True)
