function _writeText(path, text)
{
    var f = new File(path);
    f.open(File.WriteOnly);
    var s = new TextStream(f);
    s.write(text);
    f.close();
}

function _appendText(path, text)
{
    var f = new File(path);
    f.open(File.ReadWrite);
    var s = new TextStream(f);
    s.pos = f.size;
    s.write(text);
    f.close();
}

function _readBytes(path)
{
    var f = new File(path);
    if (!f.open(File.ReadOnly)) {
        return undefined;
    }
    var s = new BinaryStream(f);
    var bytes = s.readBytes(f.size);
    f.close();
    return bytes;
}

function _activeSpectrum()
{
    var spectrum = new NMRSpectrum(nmr.activeSpectrum());
    if (!spectrum.isValid()) {
        spectrum = new NMRSpectrum(mainWindow.activeDocument.getActiveItem("NMR Spectrum"));
    }
    return spectrum;
}

function _selectFirstNmrItem(statusPath)
{
    try {
        var window = mainWindow.activeWindow();
        var page = window.curPage();
        var count = page.itemCount("NMR Spectrum");
        if (count < 1) {
            _appendText(statusPath, "SELECT no NMR items\n");
            return;
        }
        var item = page.item(0, "NMR Spectrum");
        window.setSelection([item]);
        window.setActive(item);
        window.update();
        _appendText(statusPath, "SELECT first NMR item\n");
    } catch (e) {
        _appendText(statusPath, "SELECT_ERROR " + e + "\n");
    }
}

function _exportPage(imagePath)
{
    mainWindow.activeWindow().update();
    var page = mainWindow.activeDocument.curPage();
    var pixmap = draw.toPixmap(page, 300);
    pixmap.save(imagePath, "PNG");
}

function validateMNGPClipboard(inputPath, profilePath, mimeName, imagePath, statusPath)
{
    try {
        _writeText(statusPath, "START input=" + inputPath + "\nprofile=" + profilePath + "\nmime=" + mimeName + "\n");
        mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _appendText(statusPath, "ERROR could not open input\n");
            Application.quit();
            return;
        }

        var spectrum = _activeSpectrum();
        if (!spectrum.isValid()) {
            _appendText(statusPath, "ERROR no active spectrum\n");
            Application.quit();
            return;
        }
        _appendText(statusPath, "ACTIVE subtype=" + spectrum.subtype + "\n");
        _selectFirstNmrItem(statusPath);

        var bytes = _readBytes(profilePath);
        if (bytes === undefined) {
            _appendText(statusPath, "ERROR could not read profile\n");
            Application.quit();
            return;
        }
        _appendText(statusPath, "PROFILE_BYTES " + bytes.size + "\n");

        Application.clipboard.setData(mimeName, bytes);
        _appendText(statusPath, "CLIPBOARD_FORMATS " + Application.clipboard.formats.join("|") + "\n");
        mainWindow.doAction("nmrPasteProperties");
        mainWindow.activeWindow().update();
        _appendText(statusPath, "PASTE_ACTION_DONE\n");

        _exportPage(imagePath);
        _appendText(statusPath, "IMAGE " + imagePath + "\nDONE\n");
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
    }
    Application.quit();
}

function validateMNGPOpenProfile(inputPath, profilePath, openMode, imagePath, statusPath)
{
    try {
        _writeText(statusPath, "START input=" + inputPath + "\nprofile=" + profilePath + "\nmode=" + openMode + "\n");
        mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _appendText(statusPath, "ERROR could not open input\n");
            Application.quit();
            return;
        }

        var spectrum = _activeSpectrum();
        if (!spectrum.isValid()) {
            _appendText(statusPath, "ERROR no active spectrum\n");
            Application.quit();
            return;
        }
        _appendText(statusPath, "ACTIVE subtype=" + spectrum.subtype + "\n");

        if (openMode === "serialization.open") {
            _appendText(statusPath, "OPEN_PROFILE_RESULT " + serialization.open(profilePath) + "\n");
        } else if (openMode === "serialization.importFile") {
            _appendText(statusPath, "IMPORT_PROFILE_RESULT " + serialization.importFile(profilePath) + "\n");
        } else if (openMode === "mainWindow.open") {
            _appendText(statusPath, "MAINWINDOW_OPEN_PROFILE\n");
            mainWindow.open(profilePath);
        } else {
            _appendText(statusPath, "ERROR unknown open mode\n");
        }

        mainWindow.activeWindow().update();
        _exportPage(imagePath);
        _appendText(statusPath, "IMAGE " + imagePath + "\nDONE\n");
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
    }
    Application.quit();
}

function dumpMNGPBinaryStream(profilePath, statusPath)
{
    try {
        _writeText(statusPath, "START profile=" + profilePath + "\n");
        var f = new File(profilePath);
        if (!f.open(File.ReadOnly)) {
            _appendText(statusPath, "ERROR could not open profile\n");
            Application.quit();
            return;
        }
        var s = new BinaryStream(f);
        try {
            _appendText(statusPath, "STRING1 " + s.readString() + "\n");
        } catch (stringError) {
            _appendText(statusPath, "STRING1_ERROR " + stringError + "\n");
        }
        try {
            var obj = s.readObj();
            _appendText(statusPath, "OBJ " + obj + "\n");
            _appendText(statusPath, "OBJ_TYPE " + typeof obj + "\n");
            for (var key in obj) {
                _appendText(statusPath, "OBJ_KEY " + key + "=" + obj[key] + "\n");
            }
        } catch (objError) {
            _appendText(statusPath, "OBJ_ERROR " + objError + "\n");
        }
        f.close();
        _appendText(statusPath, "DONE\n");
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
    }
    Application.quit();
}

function validateMNGPNativeClipboardPaste(inputPath, imagePath, statusPath)
{
    try {
        _writeText(statusPath, "START native clipboard paste input=" + inputPath + "\n");
        mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _appendText(statusPath, "ERROR could not open input\n");
            Application.quit();
            return;
        }
        var spectrum = _activeSpectrum();
        if (!spectrum.isValid()) {
            _appendText(statusPath, "ERROR no active spectrum\n");
            Application.quit();
            return;
        }
        _appendText(statusPath, "ACTIVE subtype=" + spectrum.subtype + "\n");
        _selectFirstNmrItem(statusPath);
        _appendText(statusPath, "CLIPBOARD_FORMATS_BEFORE " + Application.clipboard.formats.join("|") + "\n");
        mainWindow.doAction("nmrPasteProperties");
        mainWindow.activeWindow().update();
        _appendText(statusPath, "PASTE_ACTION_DONE\n");
        _exportPage(imagePath);
        _appendText(statusPath, "IMAGE " + imagePath + "\nDONE\n");
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
    }
    Application.quit();
}
