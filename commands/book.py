from commands import Command
import settings


class Book(Command):
    _name = "book"
    _command_aliases = settings.readarr_book_command_aliases
    _validation_checks = ["_validate_authenticated", "_validate_readarr_enabled"]

    def _action(self, update, context):
        self._search_collection(
            update=update, 
            kind="book", 
            plural="book", 
            search_function=self.searcharr.readarr.lookup_book, 
            command_aliases=settings.readarr_book_command_aliases
        )