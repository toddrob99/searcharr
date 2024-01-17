from commands import Command
import settings


class Movie(Command):
    _name = "movie"
    _command_aliases = settings.radarr_movie_command_aliases
    _validation_checks = ["_validate_authenticated", "_validate_radarr_enabled"]

    def _action(self, update, context):
        self._search_collection(
            update=update,
            context=context, 
            kind="movie", 
            plural="movies", 
            search_function=self.searcharr.radarr.lookup_movie, 
            command_aliases=settings.radarr_movie_command_aliases
        )