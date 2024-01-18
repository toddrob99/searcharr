from commands import Command
import settings


class Series(Command):
    _name = "series"
    _command_aliases = settings.sonarr_series_command_aliases
    _validation_checks = ['_validate_authenticated', '_validate_sonarr_enabled']

    def _action(self, update, context):
        self._search_collection(
            update=update,
            context=context,
            kind="series",
            plural="series",
            search_function=self.searcharr.sonarr.lookup_series,
            command_aliases=settings.sonarr_series_command_aliases
        )
