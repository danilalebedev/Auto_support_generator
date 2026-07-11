function _writeText(path, text)
{
    var f = new File(path);
    f.open(File.WriteOnly);
    var s = new TextStream(f);
    s.write(text);
    f.close();
}

function openNmrPropertiesDialog(inputPath, statusPath)
{
    try {
        _writeText(statusPath, "START input=" + inputPath + "\n");
        mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _writeText(statusPath, "ERROR could not open input\n");
            return;
        }
        var window = mainWindow.activeWindow();
        var page = window.curPage();
        if (page.itemCount("NMR Spectrum") < 1) {
            _writeText(statusPath, "ERROR no NMR items\n");
            return;
        }
        var item = page.item(0, "NMR Spectrum");
        window.setSelection([item]);
        window.setActive(item);
        window.update();
        _writeText(statusPath, "SELECTED\nOPEN_PROPERTIES\n");
        mainWindow.doAction("action_Edit_Properties");
        _writeText(statusPath, "ACTION_RETURNED\n");
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
    }
}
