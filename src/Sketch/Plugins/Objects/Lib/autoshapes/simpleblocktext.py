###Sketch Config
#type = PluginCompound
#class_name = 'Blocktext'
#menu_text = 'Blocktext'
#standard_messages = 1
#load_immediately = 1
###End

from lib.blocktext import Blocktext, BlocktextEditor
from Sketch import RegisterCommands

RegisterCommands(Blocktext)
RegisterCommands(BlocktextEditor)
