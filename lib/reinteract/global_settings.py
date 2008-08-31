# This module holds preferences and options that are global to the entire program.

import gobject

class GlobalSettings(gobject.GObject):
    dialogs_dir = gobject.property(type=str)
    use_hildon = gobject.property(type=bool, default=False)

global_settings = GlobalSettings()
