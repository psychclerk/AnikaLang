class AnikaPlugin:
    """Base class for all AnikaLang plugins."""
    def register(self, env, interpreter):
        """
        Register plugin functions into the interpreter's environment.
        
        Args:
            env: The Environment object where NativeFunctions should be defined.
            interpreter: The Interpreter instance, useful for accessing state or other utilities.
        """
        raise NotImplementedError("Plugins must implement the register method.")