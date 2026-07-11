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

function _methodExists(target, methodName)
{
    try {
        return target !== undefined && target !== null && target[methodName] !== undefined;
    } catch (e) {
        return false;
    }
}

function _targetName(index)
{
    var names = ["spectrum", "mainWindow", "Application", "document", "page", "activeItem", "activeWindow", "nmr", "draw"];
    return names[index] || ("target" + index);
}

function _targets(spectrum)
{
    var doc, page, activeItem, activeWindow;
    var result = [spectrum];
    try {
        result.push(mainWindow);
    } catch (mainWindowError) {
        result.push(null);
    }
    try {
        result.push(Application);
    } catch (applicationError) {
        result.push(null);
    }
    try {
        doc = mainWindow.activeDocument;
        result.push(doc);
        page = doc.curPage();
        result.push(page);
        activeItem = doc.getActiveItem("NMR Spectrum");
        result.push(activeItem);
    } catch (e) {
        result.push(null);
        result.push(null);
        result.push(null);
    }
    try {
        activeWindow = mainWindow.activeWindow();
        result.push(activeWindow);
    } catch (windowError) {
        result.push(null);
    }
    try {
        result.push(nmr);
    } catch (nmrError) {
        result.push(null);
    }
    try {
        result.push(draw);
    } catch (drawError) {
        result.push(null);
    }
    return result;
}

function _applyProfileBuiltInOnly(spectrum, profilePath, statusPath)
{
    var methods = [
        "loadProperties",
        "loadGraphicProperties",
        "loadGraphicPropertiesFromFile",
        "loadGraphicsProfile",
        "loadNMRGraphicProperties",
        "loadNMRGraphicsProfile",
        "importProperties",
        "importGraphicProperties",
        "applyProperties",
        "applyGraphicProperties",
        "applyGraphicPropertiesFromFile",
        "readProperties",
        "applyGraphicsProfile"
    ];
    var targets = _targets(spectrum);
    var i, j, target, methodName;
    for (i = 0; i < targets.length; i++) {
        target = targets[i];
        if (target === undefined || target === null) {
            _appendText(statusPath, "TARGET " + _targetName(i) + " null\n");
            continue;
        }
        for (j = 0; j < methods.length; j++) {
            methodName = methods[j];
            if (_methodExists(target, methodName)) {
                _appendText(statusPath, "METHOD_EXISTS " + _targetName(i) + "." + methodName + "\n");
                try {
                    target[methodName](profilePath);
                    _appendText(statusPath, "APPLIED " + _targetName(i) + "." + methodName + "\n");
                    return true;
                } catch (e) {
                    _appendText(statusPath, "FAILED " + _targetName(i) + "." + methodName + ": " + e + "\n");
                }
            }
        }
    }
    _appendText(statusPath, "NO_BUILTIN_METHOD_APPLIED\n");
    return false;
}

function validateMNGPBuiltIn(inputPath, profilePath, imagePath, statusPath)
{
    try {
        _writeText(statusPath, "START input=" + inputPath + " profile=" + profilePath + "\n");
        mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _writeText(statusPath, "ERROR could not open input\n");
            Application.quit();
            return;
        }
        mainWindow.activeWindow().update();
        var doc = mainWindow.activeDocument;
        var spectrum = new NMRSpectrum(nmr.activeSpectrum());
        if (!spectrum.isValid()) {
            spectrum = new NMRSpectrum(doc.getActiveItem("NMR Spectrum"));
        }
        if (!spectrum.isValid()) {
            _writeText(statusPath, "ERROR no active NMR spectrum\n");
            Application.quit();
            return;
        }
        _appendText(statusPath, "ACTIVE subtype=" + spectrum.subtype + "\n");
        _applyProfileBuiltInOnly(spectrum, profilePath, statusPath);
        mainWindow.activeWindow().update();
        var page = mainWindow.activeDocument.curPage();
        var pixmap = draw.toPixmap(page, 300);
        pixmap.save(imagePath, "PNG");
        _appendText(statusPath, "IMAGE " + imagePath + "\nDONE\n");
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
    }
    Application.quit();
}
