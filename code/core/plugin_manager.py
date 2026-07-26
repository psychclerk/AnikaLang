import os
import importlib.util
import inspect
import sys

class PluginManager:
    def __init__(self, plugins_dir):
        self.plugins_dir = plugins_dir
        
    def load_plugins(self, env, interpreter):
        if not os.path.exists(self.plugins_dir):
            print(f"Warning: Plugins directory not found: {self.plugins_dir}")
            return
            
        # Ensure plugins_dir parent is in sys.path so 'core' and 'plugins' can be imported
        parent_dir = os.path.dirname(self.plugins_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
            
        # Ensure the 'plugins' package is initialized in sys.modules
        if 'plugins' not in sys.modules:
            try:
                import plugins
            except ImportError:
                pass
                
        for filename in sorted(os.listdir(self.plugins_dir)):
            if filename.startswith("plugin_") and filename.endswith(".py"):
                base_name = filename[:-3]
                
                # CRITICAL FIX: Use the fully qualified package name
                module_name = f"plugins.{base_name}"
                filepath = os.path.join(self.plugins_dir, filename)
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    module = importlib.util.module_from_spec(spec)
                    
                    # CRITICAL FIX: Set the package context so relative imports work
                    module.__package__ = "plugins"
                    
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    # Find the plugin class
                    from plugins.base_plugin import AnikaPlugin
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, AnikaPlugin) and obj is not AnikaPlugin:
                            plugin_instance = obj()
                            plugin_instance.register(env, interpreter)
                            print(f"Loaded plugin: {base_name}")
                            break
                except Exception as e:
                    print(f"Failed to load plugin {filename}: {e}")