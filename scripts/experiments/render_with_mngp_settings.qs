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

function _readMNGPSpectrumProperties(profilePath, statusPath)
{
    var file = new File(profilePath);
    if (!file.open(File.ReadOnly)) {
        throw "Could not open MNGP file: " + profilePath;
    }

    var stream = new BinaryStream(file);
    stream.endianness = BinaryStream.eBig;

    var header = stream.readString();
    _appendText(statusPath, "MNGP_HEADER " + header + "\n");
    if (header !== "MestReNova Graphic Properties") {
        throw "Unsupported MNGP header: " + header;
    }

    // The properties file stores several page/item fields before the actual
    // NMR Spectrum Properties QByteArray. We read them with BinaryStream, then
    // read the payload by its declared length. This mirrors Mnova's own
    // QDataStream layout and avoids editing individual bytes/settings.
    _appendText(statusPath, "POS_AFTER_HEADER " + stream.pos + "\n");
    var field1 = stream.readInt32();
    var field2 = stream.readInt32();
    var field3 = stream.readInt32();
    var field4 = stream.readInt32();
    _appendText(statusPath, "FIELD_INT_1 " + field1 + "\n");
    _appendText(statusPath, "FIELD_INT_2 " + field2 + "\n");
    _appendText(statusPath, "FIELD_INT_3 " + field3 + "\n");
    _appendText(statusPath, "FIELD_INT_4 " + field4 + "\n");
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    _appendText(statusPath, "POS_AFTER_REALS " + stream.pos + "\n");
    var beforePayload = stream.readInt8();
    _appendText(statusPath, "FIELD_BEFORE_PAYLOAD " + beforePayload + " POS " + stream.pos + "\n");

    var payloadSize = stream.readInt32();
    _appendText(statusPath, "MNGP_PAYLOAD_SIZE " + payloadSize + "\n");
    if (payloadSize <= 0 || payloadSize > 10000000) {
        throw "Invalid MNGP payload size: " + payloadSize;
    }
    return stream.readBytes(payloadSize);
}

function _applyMNGPAsDefault(profilePath, statusPath)
{
    var payload = _readMNGPSpectrumProperties(profilePath, statusPath);
    var nmrSettings = new Settings("NMR");
    var previous = nmrSettings.value("Spectrum Properties", new ByteArray());
    nmrSettings.setValue("Spectrum Properties", payload);
    var stored = nmrSettings.value("Spectrum Properties", new ByteArray());
    try {
        _appendText(statusPath, "SETTINGS_PREVIOUS_SIZE " + previous.size + "\n");
        _appendText(statusPath, "SETTINGS_STORED_SIZE " + stored.size + "\n");
    } catch (e) {
        _appendText(statusPath, "SETTINGS_STORED_SIZE unavailable\n");
    }
    return previous;
}

function _restoreMNGPDefault(previousPayload, statusPath)
{
    if (previousPayload === undefined || previousPayload === null) {
        return;
    }
    try {
        var nmrSettings = new Settings("NMR");
        nmrSettings.setValue("Spectrum Properties", previousPayload);
        _appendText(statusPath, "SETTINGS_RESTORED\n");
    } catch (e) {
        _appendText(statusPath, "SETTINGS_RESTORE_ERROR " + e + "\n");
    }
}

function renderWithMNGPSettings(inputPath, profilePath, imagePath, statusPath)
{
    var previousPayload = null;
    try {
        _writeText(statusPath, "START input=" + inputPath + " profile=" + profilePath + "\n");
        previousPayload = _applyMNGPAsDefault(profilePath, statusPath);

        mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _writeText(statusPath, "ERROR could not open input\n");
            _restoreMNGPDefault(previousPayload, statusPath);
            Application.quit();
            return;
        }

        var window = mainWindow.activeWindow();
        var page = window.curPage();
        if (page.itemCount("NMR Spectrum") < 1) {
            _writeText(statusPath, "ERROR no NMR items\n");
            Application.quit();
            return;
        }

        var item = page.item(0, "NMR Spectrum");
        window.setSelection([item]);
        window.setActive(item);
        window.update();

        var spectrum = new NMRSpectrum(item);
        _appendText(statusPath, "GRID_H " + spectrum.getProperty("grid.showhorizontal") + "\n");
        _appendText(statusPath, "GRID_V " + spectrum.getProperty("grid.showvertical") + "\n");
        _appendText(statusPath, "PEAKS_SHOW " + spectrum.getProperty("peaks.show") + "\n");

        var pixmap = draw.toPixmap(page, 300);
        pixmap.save(imagePath, "PNG");
        _restoreMNGPDefault(previousPayload, statusPath);
        _appendText(statusPath, "IMAGE " + imagePath + "\nDONE\n");
    } catch (e) {
        _restoreMNGPDefault(previousPayload, statusPath);
        _appendText(statusPath, "ERROR " + e + "\n");
    }
    Application.quit();
}
