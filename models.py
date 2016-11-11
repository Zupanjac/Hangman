"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb


class User(ndb.Model):
    """User profile"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    date_created = ndb.DateTimeProperty(auto_now_add=True)
    
    @classmethod
    def create_user(cls, user_name, email):
        """Create user in the database"""
        p_key = ndb.Key(User, user_name)
        user = User(key=p_key,
                    name=user_name,
                    email=email)
        user.put()
        return user;
    

class GameHistory(ndb.Model):
    """Game history object"""
    guess = ndb.StringProperty(required=True)
    found = ndb.BooleanProperty(required=True)
    index = ndb.IntegerProperty(required=True)
    message = ndb.StringProperty(required=True)
    date_created = ndb.DateTimeProperty(auto_now_add=True)
    
    def to_form(self):
        form = GameHistoryForm()
        form.guess = self.guess
        form.found = self.found
        form.index = self.index
        form.message = self.message
        return form
    
    @classmethod
    def create_game_history(cls, game, guess, found, index, message):
        game_history = GameHistory(parent=ndb.Key(Game, game),
                                   guess=guess, found=found, index=index, message=message)
        game_history.put()
        

class Game(ndb.Model):
    """Game object"""
    guess_word = ndb.StringProperty(required=True)
    word_in_progress = ndb.StringProperty(required=True)
    user = ndb.KeyProperty(required=True, kind='User')
    attempts_allowed = ndb.IntegerProperty(required=True, default=10)
    attempts_remaining = ndb.IntegerProperty(required=True, default=10)
    game_over = ndb.BooleanProperty(required=True, default=False)
    canceled = ndb.BooleanProperty(required=True, default=False)
    date_created = ndb.DateTimeProperty(auto_now_add=True)
    
    @classmethod
    def create_game(cls, user):
        """Creates and returns a new game"""
        words = ['HANGMAN', 'ZOO', 'PYTHON', 'GRANDMOTHER',
                 'RELATIONSHIP', 'SWIFT', 'PRESIDENT']
        target_word = random.choice(words)
        temp = ['_'] * (len(target_word))
        word_in_progress = ''.join(temp)
        game = Game(parent=user,
                    guess_word=target_word,
                    user=user,
                    word_in_progress=word_in_progress)
        
        game.put()
        return game

    def to_form(self, message):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.word_in_progress = ' '.join(self.word_in_progress)
        form.canceled = self.canceled
        form.game_over = self.game_over
        form.attempts_allowed = self.attempts_allowed
        form.attempts_remaining = self.attempts_remaining
        form.message = message
        return form

    def end_game(self, won=False):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True
        self.put()
        # Add the game to the score 'board'
        score = Score(user=self.user, date=date.today(), won=won,
                      guesses=self.attempts_allowed - self.attempts_remaining)
        score.put()


class Score(ndb.Model):
    """Score object"""
    user = ndb.KeyProperty(required=True, kind='User')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True)
    guesses = ndb.IntegerProperty(required=True)

    def to_form(self):
        return ScoreForm(user_name=self.user.get().name, won=self.won,
                         date=str(self.date), guesses=self.guesses)
    
    
class GameHistoryForm(messages.Message):
    """GameHistoryForm get moves in game"""
    guess = messages.StringField(1, required=True)
    found = messages.BooleanField(2, required=True)
    index = messages.IntegerField(3, required=True)
    message = messages.StringField(4, required=True)


class GameForm(messages.Message):
    """GameForm for outbound game move information"""
    urlsafe_key = messages.StringField(1, required=True)
    word_in_progress = messages.StringField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    canceled = messages.BooleanField(4, required=True)
    attempts_allowed = messages.IntegerField(6, required=True)
    attempts_remaining = messages.IntegerField(7, required=True)
    message = messages.StringField(8, required=True)


class GameHistoryForms(messages.Message):
    """Used to receive all active games for specific user"""
    items = messages.MessageField(GameHistoryForm, 1, repeated=True)
    
    
class GameForms(messages.Message):
    """Uses to receive information  about the game status"""
    items = messages.MessageField(GameForm, 1, repeated=True)
 

class NewGameForm(messages.Message):
    """Used to create a new game"""
    user_name = messages.StringField(1, required=True)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    guess = messages.StringField(1, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    guesses = messages.IntegerField(4, required=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
