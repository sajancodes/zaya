"""Package the maintained webrtcvad-wheels distribution used by Zaya."""

from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata('webrtcvad-wheels')
hiddenimports = ['_webrtcvad']
