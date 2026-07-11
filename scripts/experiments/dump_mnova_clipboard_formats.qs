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

function dumpClipboardFormats(inputPath, outputPath, statusPath)
{
    try {
        _writeText(statusPath, "START input=" + inputPath + "\n");
        mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _writeText(statusPath, "ERROR could not open input\n");
            Application.quit();
            return;
        }
        mainWindow.activeWindow().update();
        var window = mainWindow.activeWindow();
        var page = window.curPage();
        if (page.itemCount("NMR Spectrum") < 1) {
            _writeText(statusPath, "ERROR no NMR items\n");
            Application.quit();
            return;
        }
        var spectrum = page.item(0, "NMR Spectrum");
        window.setSelection([spectrum]);
        window.setActive(spectrum);
        window.update();
        _appendText(statusPath, "SELECTED\n");
        mainWindow.doAction("action_Edit_Copy");
        _appendText(statusPath, "COPIED\n");
        mainWindow.activeWindow().update();
        var formats = Application.clipboard.formats;
        var lines = [];
        var i, fmt, data, safePath, bf, bs;
        lines.push("formats=" + formats.length);
        for (i = 0; i < formats.length; i++) {
            fmt = String(formats[i]);
            try {
                data = Application.clipboard.data(fmt);
                lines.push(fmt + "\t" + data.size);
                safePath = outputPath + "." + fmt.replace(/[^A-Za-z0-9_.-]/g, "_") + ".bin";
                bf = new File(safePath);
                bf.open(File.WriteOnly);
                bs = new BinaryStream(bf);
                bs.writeBytes(data);
                bf.close();
            } catch (e) {
                lines.push(fmt + "\tERROR " + e);
            }
        }
        _writeText(outputPath, lines.join("\n") + "\n");
        _appendText(statusPath, "DONE\n");
    } catch (e) {
        _writeText(statusPath, "ERROR " + e + "\n");
    }
    Application.quit();
}
