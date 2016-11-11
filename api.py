# -*- coding: utf-8 -*-`
"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""

import endpoints
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from models import User, Game, Score, GameForms, GameHistory, GameHistoryForms
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm, \
    ScoreForms
from utils import get_by_urlsafe

# Uses for new game request
NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
# Used for getting game info
GET_GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1), )
# Get the game moves for game
GET_GAME_HISTORY = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1), )
# Make an move
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1), )
# Information about the user
USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))

GET_USER_GAME = endpoints.ResourceContainer(user_name=messages.StringField(1))
GET_HIGH_SCORE = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                             number_of_results=messages.IntegerField(2))
MEMCACHE_MOVES_REMAINING = 'MOVES_REMAINING'


@endpoints.api(name='hangman', version='1.0')
class HangmanApi(remote.Service):
    """Hangman Game API"""
    
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create user api"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists'
            )
        # If the user is not given in parameter throw exception
        if not request.user_name:
            raise endpoints.BadRequestException(
                'Name of the user not given'
            )
        # Ok create the user and return message
        user = User.create_user(request.user_name, request.email)
        return StringMessage(message='User {} created!'.format(
            user.name))
    
    @endpoints.method(request_message=GET_HIGH_SCORE,
                      response_message=ScoreForms,
                      path='game_high_score',
                      name='get_high_score',
                      http_method='GET')
    def get_high_score(self, request):
        """Create game api"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A user whit that name does not exists')
        # Get score from table order by won games ascending by guesses
        scores = Score.query(Score.user == user.key).order(Score.won).order(Score.guesses)
        if scores.get() is None:
            raise endpoints.NotFoundException(
                'No games finished till now for user')
        if request.number_of_results > 0:
            scores = scores.fetch(request.number_of_results)
        return ScoreForms(items=[score.to_form() for score in scores])
    
    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='create_game',
                      http_method='POST')
    def create_game(self, request):
        """Create game api"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A user whit that name does not exists')
        
        game = Game.create_game(user.key)
        taskqueue.add(url='/tasks/send_reminder')
        return game.to_form('Good luck playing Hangman!')
    
    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameHistoryForms,
                      path='game/{urlsafe_game_key}',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Return the game history."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)

        # If the game dose't exist throw exception.
        if not game:
            raise endpoints.NotFoundException('Game not found!')
        
        game_key = ndb.Key(Game, request.urlsafe_game_key)
        return GameHistoryForms(items=[game_history.to_form()
                                       for game_history in
                                       GameHistory.query(ancestor=game_key).order(GameHistory.date_created)]
                                )
    
    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=StringMessage,
                      path='game/{urlsafe_game_key}',
                      name='cancel_game',
                      http_method='POST')
    def cancel_game(self, request):
        """Cancel game API."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game and game.game_over == False and game.canceled == False:
            game.canceled = True;
            game.end_game(False)
            game.put()
        else:
            raise endpoints.NotFoundException('Game not found!')
        
        return StringMessage(message="Game canceled")
    
    @endpoints.method(request_message=GET_USER_GAME,
                      response_message=GameForms,
                      path='user_games',
                      name='get_user_games',
                      http_method='POST')
    def get_user_games(self, request):
        """Get user active games"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'User not found')
        ancestor_key = ndb.Key(User, user.name)
        # Get user games that are still active
        return GameForms(items=[game.to_form('Game online')
                                for game in Game.query(ancestor=ancestor_key).filter(
                Game.game_over == False, Game.canceled == False)])
    
    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        # Check if the game is finished
        if game.game_over:
            return game.to_form('Game already finished!')
        
        # Only alphabetic character is allowed
        if not request.guess.isalpha():
            return game.to_form('Only alphabetic character is allowed!')
        guess = request.guess.upper()
        
        # Only one character is allowed
        if len(guess) != 1:
            return game.to_form('Only one character allowed')
        
        # We will check if the character is already used
        game_key = ndb.Key(Game, request.urlsafe_game_key)
        ls = GameHistory.query(ancestor=game_key).filter(
            GameHistory.guess == guess).count()
        if ls != 0:
            return game.to_form('Character already used' + guess)
        
        found = False
        temp = list(game.guess_word)
        temp_wimp = list(game.word_in_progress)
        for i, val in enumerate(temp):
            if val == guess:
                temp_wimp[i] = guess
                found = True
                msg = 'Key found ' + guess
                GameHistory.create_game_history(request.urlsafe_game_key, guess, found, i, 'Found')
        
        game.word_in_progress = ''.join(temp_wimp)
        
        if found is False:
            GameHistory.create_game_history(request.urlsafe_game_key, guess, found, -1, 'Not found')
            game.attempts_remaining -= 1
            msg = 'Character not found in word: ' + request.guess
        
        if game.word_in_progress == game.guess_word:
            game.end_game(True)
            msg = 'You win'
        
        if game.attempts_remaining < 1:
            game.end_game(False)
            GameHistory.create_game_history(request.urlsafe_game_key,
                                            guess, found, -1, 'Not attempts remaining you lose')
            return game.to_form(msg + ' Game over!')
        else:
            game.put()
            return game.to_form(msg)


@endpoints.api(name='guess_a_number', version='v1')
class GuessANumberApi(remote.Service):
    """Game API"""
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=StringMessage,
                      path='user',
                      name='create_user',
                      http_method='POST')
    def create_user(self, request):
        """Create a User. Requires a unique username"""
        if User.query(User.name == request.user_name).get():
            raise endpoints.ConflictException(
                'A User with that name already exists!')
        user = User(name=request.user_name, email=request.email)
        user.put()
        # Return the confirmation of user created
        return StringMessage(message='User {} created!'.format(
            request.user_name))
    
    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """Creates new game"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        try:
            game = Game.new_game(user, request.min,
                                 request.max, request.attempts)
        except ValueError:
            raise endpoints.BadRequestException('Maximum must be greater '
                                                'than minimum!')
        
        # Use a task queue to update the average attempts remaining.
        # This operation is not needed to complete the creation of a new game
        # so it is performed out of sequence.
        taskqueue.add(url='/tasks/cache_average_attempts')
        return game.to_form('Good luck playing Guess a Number!')
    
    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Return the current game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_form('Time to make a move!')
        else:
            raise endpoints.NotFoundException('Game not found!')
    
    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move. Returns a game state with message"""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game already over!')
        
        game.attempts_remaining -= 1
        if request.guess == game.guess_wordn:
            game.end_game(True)
            return game.to_form('You win!')
        
        if request.guess < game.guess_word:
            msg = 'Too low!'
        else:
            msg = 'Too high!'
        
        if game.attempts_remaining < 1:
            game.end_game(False)
            return game.to_form(msg + ' Game over!')
        else:
            game.put()
            return game.to_form(msg)
    
    @endpoints.method(response_message=ScoreForms,
                      path='scores',
                      name='get_scores',
                      http_method='GET')
    def get_scores(self, request):
        """Return all scores"""
        return ScoreForms(items=[score.to_form() for score in Score.query()])
    
    @endpoints.method(request_message=USER_REQUEST,
                      response_message=ScoreForms,
                      path='scores/user/{user_name}',
                      name='get_user_scores',
                      http_method='GET')
    def get_user_scores(self, request):
        """Returns all of an individual User's scores"""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                'A User with that name does not exist!')
        scores = Score.query(Score.user == user.key)
        return ScoreForms(items=[score.to_form() for score in scores])
    
    @endpoints.method(response_message=StringMessage,
                      path='games/average_attempts',
                      name='get_average_attempts_remaining',
                      http_method='GET')
    def get_average_attempts(self, request):
        """Get the cached average moves remaining"""
        return StringMessage(message=memcache.get(MEMCACHE_MOVES_REMAINING) or '')
    
    @staticmethod
    def _cache_average_attempts():
        """Populates memcache with the average moves remaining of Games"""
        games = Game.query(Game.game_over == False).fetch()
        if games:
            count = len(games)
            total_attempts_remaining = sum([game.attempts_remaining
                                            for game in games])
            average = float(total_attempts_remaining) / count
            memcache.set(MEMCACHE_MOVES_REMAINING,
                         'The average moves remaining is {:.2f}'.format(average))


api = endpoints.api_server([HangmanApi])
