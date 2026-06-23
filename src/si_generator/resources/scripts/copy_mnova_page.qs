function _writeText(path, text)
{
    var f = new File(path);
    f.open(File.WriteOnly);
    var s = new TextStream(f);
    s.write(text);
    f.close();
}

function copyMnovaPageToClipboard(mnovaPath, pageIndexText, statusPath, actionName)
{
    try {
        _writeText(statusPath, "START " + mnovaPath + " page=" + pageIndexText + "\n");
        var pageIndex = parseInt(pageIndexText, 10);
        if (isNaN(pageIndex) || pageIndex < 0) {
            _writeText(statusPath, "ERROR invalid page index: " + pageIndexText + "\n");
            Application.quit();
            return;
        }

        var dw = mainWindow.newWindow();
        if (!serialization.open(mnovaPath)) {
            _writeText(statusPath, "ERROR could not open " + mnovaPath + "\n");
            Application.quit();
            return;
        }

        var doc = mainWindow.activeDocument;
        if (!doc || doc.pageCount() <= pageIndex) {
            _writeText(statusPath, "ERROR page " + pageIndex + " does not exist; pageCount=" + (doc ? doc.pageCount() : 0) + "\n");
            Application.quit();
            return;
        }

        doc.setCurPageIndex(pageIndex);
        doc.setSelectedPages([doc.curPage()]);
        doc.setSelection([]);
        doc.update();

        mainWindow.doAction(actionName || "action_Edit_Copy");
        _writeText(statusPath, "OK copied " + mnovaPath + " page=" + pageIndex + "\n");
        Application.quit();
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
        Application.quit();
    }
}
