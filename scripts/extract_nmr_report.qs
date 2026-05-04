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

function _readText(path)
{
    var f = new File(path);
    f.open(File.ReadOnly);
    var s = new TextStream(f);
    var text = s.readAll();
    f.close();
    return text;
}

function _jsonEscape(text)
{
    return String(text)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, "\\\"")
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n")
        .replace(/\t/g, "\\t");
}

function _plainMultipletReport(spectrum, nucleus)
{
    var reporter = MultipletReporter.getReporterByName("J. Am. Chem. Soc.");
    if (reporter === undefined) {
        reporter = MultipletReporter.getDefaultReporter();
    }

    reporter.readSettings();
    reporter.useHtml = false;
    reporter.reportRange = true;
    reporter.allAsRanges = false;
    reporter.sortMultipletsAscending = false;
    reporter.sortJAscending = true;
    reporter.reducedJList = true;
    reporter.extendedSolventName = false;
    reporter.reportJs = true;
    reporter.reportAssignments = false;
    reporter.deltaPrecision = nucleus === "13C" ? 1 : 2;
    reporter.jPrecision = 1;

    return reporter.report(spectrum, false);
}

function _referenceValue(spectrum, nucleus)
{
    var solvent = String(spectrum.solvent || "").toLowerCase();
    if (solvent.indexOf("dmso") >= 0) {
        return nucleus === "13C" ? 39.52 : 2.50;
    }
    return nucleus === "13C" ? 77.16 : 7.26;
}

function _referenceSpectrum(spectrum, nucleus)
{
    var reference = _referenceValue(spectrum, nucleus);
    var tolerance = nucleus === "13C" ? 1.0 : 0.15;

    try {
        spectrum.reference(1, reference, reference, true, tolerance, "CHCl3 reference");
        spectrum.update();
    } catch (e) {
        // Referencing is best-effort: if Mnova cannot find CHCl3/CDCl3, keep the
        // spectrum usable and report the unreferenced peak list.
    }
}

function _processForReport(spectrum, nucleus, sensitivity, doReference, applyBaseline)
{
    var p = new NMRProcessing(spectrum.proc);

    if (doReference) {
        _referenceSpectrum(spectrum, nucleus);
    }

    if (nucleus === "13C" && applyBaseline) {
        p.setParameter("BC.Apply", true);
        p.setParameter("BC.algorithm", "Bernstein");
        p.setParameter("BC.PolyOrder", 3);
    }
    p.setParameter("PP.Apply", false);
    p.setParameter("PP.Method", "GSD");
    if (nucleus === "13C" && sensitivity !== undefined) {
        p.setParameter("PP.Sensitivity", sensitivity);
    }
    spectrum.process(p);

    p.setParameter("Mult.Apply", false);
    p.setParameter("integration.apply", false);
    spectrum.process(p);

    if (nucleus === "13C" && applyBaseline) {
        _clearNonPeakAnnotations(spectrum);
        spectrum.update();
        return;
    }

    p.setParameter("integration.method", "Auto");
    p.setParameter("integration.apply", true);
    p.setParameter("Mult.Apply", true);
    spectrum.process(p);
    spectrum.update();
}

function _clearNonPeakAnnotations(spectrum)
{
    try {
        spectrum.setMultiplets(new Multiplets());
    } catch (e) {
    }
    try {
        spectrum.setIntegrals(new Integrals());
    } catch (e) {
    }
    try {
        spectrum.process();
    } catch (e) {
    }
}

function _hideProtonImageClutter(spectrum)
{
    try {
        spectrum.setMultiplets(new Multiplets());
    } catch (e) {
    }
    try {
        spectrum.setProperty("integrals.show", true);
        spectrum.setProperty("integrals.label.show", true);
        spectrum.setProperty("integrals.label.position", "Segment");
        spectrum.setProperty("integrals.label.margin", 2);
        spectrum.setProperty("integrals.curve.show", false);
        spectrum.setProperty("axes.margin.mm", 1.27);
        spectrum.setProperty("multiplets.show", false);
        spectrum.setProperty("multiplets.integral.curve.show", false);
        spectrum.setProperty("multiplets.integral.label.show", true);
    } catch (e) {
    }
    try {
        spectrum.update();
    } catch (e) {
    }
}

function _visibleRegion(nucleus)
{
    if (nucleus === "13C") {
        return new SpectrumRegion(-10.0, 210.0);
    }
    return new SpectrumRegion(-1.0, 12.0);
}

function _isReferencePeak(spectrum, nucleus, delta)
{
    var reference = _referenceValue(spectrum, nucleus);
    var tolerance = nucleus === "13C" ? 0.35 : 0.04;
    if (Math.abs(delta - reference) <= tolerance) {
        return true;
    }
    return nucleus === "1H" && Math.abs(delta) <= 0.05;
}

function _isIgnoredImagePeak(spectrum, nucleus, delta)
{
    if (_isReferencePeak(spectrum, nucleus, delta)) {
        return true;
    }
    if (nucleus !== "1H") {
        return false;
    }

    var solvent = String(spectrum.solvent || "").toLowerCase();
    if (solvent.indexOf("dmso") >= 0) {
        return Math.abs(delta - 3.33) <= 0.06;
    }
    return Math.abs(delta - 1.56) <= 0.08 || Math.abs(delta - 1.77) <= 0.08;
}

function _filterPeaksForImage(spectrum, nucleus)
{
    var allPeaks, keptPeaks, peak, i, intensity, maxIntensity, threshold;

    try {
        allPeaks = new Peaks(spectrum.peaks());
        if (!allPeaks || !allPeaks.count) {
            allPeaks = new Peaks(spectrum, _visibleRegion(nucleus));
        }
        maxIntensity = 0;
        for (i = 0; i < allPeaks.count; i++) {
            peak = allPeaks.at(i);
            if (_isIgnoredImagePeak(spectrum, nucleus, peak.delta())) {
                continue;
            }
            intensity = Math.abs(peak.intensity);
            if (intensity > maxIntensity) {
                maxIntensity = intensity;
            }
        }
        if (maxIntensity <= 0) {
            for (i = 0; i < allPeaks.count; i++) {
                peak = allPeaks.at(i);
                if (_isIgnoredImagePeak(spectrum, nucleus, peak.delta())) {
                    continue;
                }
                intensity = Math.abs(peak.intensity);
                if (intensity > maxIntensity) {
                    maxIntensity = intensity;
                }
            }
        }
        threshold = maxIntensity * (nucleus === "1H" ? 0.05 : 0.018);
        keptPeaks = new Peaks();
        for (i = 0; i < allPeaks.count; i++) {
            peak = allPeaks.at(i);
            if (!_isIgnoredImagePeak(spectrum, nucleus, peak.delta()) && Math.abs(peak.intensity) >= threshold) {
                if (nucleus === "1H") {
                    peak.annotation = "";
                }
                keptPeaks.append(peak);
            }
        }
        spectrum.setPeaks(keptPeaks);
    } catch (e) {
    }
}

function _fitVerticalScaleForImage(spectrum, nucleus)
{
    var peaks, peak, i, intensity, maxIntensity, minIntensity, top, bottom;

    try {
        peaks = new Peaks(spectrum, _visibleRegion(nucleus));
        if (!peaks || !peaks.count) {
            peaks = new Peaks(spectrum.peaks());
        }
        maxIntensity = 0;
        minIntensity = 0;
        for (i = 0; i < peaks.count; i++) {
            peak = peaks.at(i);
            intensity = peak.intensity;
            if (intensity > maxIntensity) {
                maxIntensity = intensity;
            }
            if (intensity < minIntensity) {
                minIntensity = intensity;
            }
        }
        if (maxIntensity > 0) {
            top = maxIntensity * 1.25;
            bottom = nucleus === "1H" ? -maxIntensity * 0.14 : (minIntensity < 0 ? minIntensity * 1.15 : -maxIntensity * 0.03);
            spectrum.vertZoom(bottom, top);
        }
    } catch (e) {
    }
}

function _plainPeakReport(spectrum, nucleus)
{
    var peaks, peak, i, delta, values, solvent, frequency, header, precision;
    var minDelta = nucleus === "13C" ? -10 : -1;
    var maxDelta = nucleus === "13C" ? 230 : 15;
    var solventReference = _referenceValue(spectrum, nucleus);
    var solventTolerance = nucleus === "13C" ? 0.35 : 0.04;

    peaks = new Peaks(spectrum, new SpectrumRegion(minDelta, maxDelta));
    if (!peaks || !peaks.count) {
        peaks = new Peaks(spectrum.peaks());
    }
    peaks.sort(false);

    values = [];
    precision = nucleus === "13C" ? 1 : 2;
    for (i = 0; i < peaks.count; i++) {
        peak = peaks.at(i);
        delta = peak.delta();
        if (nucleus === "13C" && (Math.abs(delta - solventReference) <= solventTolerance || (delta >= 76.0 && delta <= 78.2))) {
            continue;
        }
        if (delta < minDelta || delta > maxDelta) {
            continue;
        }
        values.push(delta.toFixed(precision));
    }

    solvent = spectrum.solvent || "CDCl3";
    frequency = spectrum.frequency ? spectrum.frequency().toFixed(0) : "";
    header = nucleus + " NMR (" + frequency + " MHz, " + solvent + ") δ ";
    return header + values.join(", ") + ".";
}

function _referenceOffsetFromPeaks(spectrum, nucleus)
{
    var reference = _referenceValue(spectrum, nucleus);
    var tolerance = nucleus === "13C" ? 1.2 : 0.2;
    var peaks, peak, i, bestPeak, bestDistance, distance;

    try {
        peaks = new Peaks(spectrum, new SpectrumRegion(reference - tolerance, reference + tolerance));
        bestPeak = undefined;
        bestDistance = 9999;
        for (i = 0; i < peaks.count; i++) {
            peak = peaks.at(i);
            distance = Math.abs(peak.delta() - reference);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestPeak = peak;
            }
        }
        if (bestPeak !== undefined) {
            return reference - bestPeak.delta();
        }
    } catch (e) {
    }
    return 0;
}

function _exportSpectrumImage(spectrum, nucleus, imagePath)
{
    if (!imagePath) {
        return "";
    }

    try {
        _prepareSpectrumForExport(spectrum, nucleus);
        mainWindow.activeWindow().update();

        var page = mainWindow.activeDocument.curPage();
        var pixmap = draw.toPixmap(page, 300);
        pixmap.save(imagePath, "PNG");
        return imagePath;
    } catch (e) {
        return "";
    }
}

function _prepareSpectrumForExport(spectrum, nucleus)
{
    if (nucleus === "13C") {
        _clearNonPeakAnnotations(spectrum);
    } else {
        _hideProtonImageClutter(spectrum);
    }
    _filterPeaksForImage(spectrum, nucleus);
    if (nucleus === "13C") {
        spectrum.horzZoom(-10.0, 210.0);
    } else {
        spectrum.horzZoom(-1.0, 12.0);
    }
    _fitVerticalScaleForImage(spectrum, nucleus);
    spectrum.update();
}

function _spectrumReport(spectrum, nucleus)
{
    if (nucleus === "13C") {
        return _plainPeakReport(spectrum, nucleus);
    }
    return _plainMultipletReport(spectrum, nucleus);
}

function extractSpectrumReport(inputPath, outputPath, nucleus, statusPath)
{
    try {
        _writeText(statusPath, "START input=" + inputPath + "\n");

        var dw = mainWindow.newWindow();
        _appendText(statusPath, "WINDOW\n");

        if (!serialization.open(inputPath)) {
            _writeText(statusPath, "ERROR: Could not open " + inputPath);
            Application.quit();
            return;
        }
        _appendText(statusPath, "OPENED\n");

        var spectrum = new NMRSpectrum(nmr.activeSpectrum());
        if (!spectrum.isValid()) {
            spectrum = new NMRSpectrum(mainWindow.activeDocument.getActiveItem("NMR Spectrum"));
        }
        if (!spectrum.isValid()) {
            _writeText(statusPath, "ERROR: No active NMR spectrum after opening " + inputPath);
            Application.quit();
            return;
        }
        _appendText(statusPath, "SPECTRUM\n");

        _processForReport(spectrum, nucleus, undefined, true, false);
        _appendText(statusPath, "PROCESSED\n");

        var report = _spectrumReport(spectrum, nucleus);
        _writeText(outputPath, report);
        _appendText(statusPath, "OK\n");

        dw.close();
    } catch (e) {
        _writeText(statusPath, "ERROR: " + e);
    }

    Application.quit();
}

function extractSpectrumReportsBatch(tasksPath, outputJsonPath, statusPath)
{
    var text, lines, i, line, parts, compound, nucleus, inputPath;
    var first = true;
    var json = "{\n";
    var tasks = [];

    try {
        _writeText(statusPath, "START batch tasks=" + tasksPath + "\n");
        text = _readText(tasksPath);
        lines = text.split(/\r?\n/);

        for (i = 0; i < lines.length; i++) {
            line = lines[i];
            if (!line || line.replace(/\s/g, "") === "") {
                continue;
            }
            parts = line.split("\t");
            if (parts.length < 3) {
                _appendText(statusPath, "SKIP malformed line " + (i + 1) + "\n");
                continue;
            }

            compound = parts[0];
            nucleus = parts[1];
            inputPath = parts[2];
            var imagePath = parts.length >= 4 ? parts[3] : "";
            var mnovaPath = parts.length >= 5 ? parts[4] : "";
            tasks.push({compound: compound, nucleus: nucleus, inputPath: inputPath, imagePath: imagePath, mnovaPath: mnovaPath});
            _appendText(statusPath, "TASK " + compound + " " + nucleus + " " + inputPath + "\n");

            var dw = mainWindow.newWindow();
            var report = "";
            var peakReport = "";
            var image = "";
            var mnova = mnovaPath;
            var referenceOffset = 0;
            var error = "";

            try {
                if (!serialization.open(inputPath)) {
                    error = "Could not open " + inputPath;
                } else {
                    var spectrum = new NMRSpectrum(nmr.activeSpectrum());
                    if (!spectrum.isValid()) {
                        spectrum = new NMRSpectrum(mainWindow.activeDocument.getActiveItem("NMR Spectrum"));
                    }
                    if (!spectrum.isValid()) {
                        error = "No active NMR spectrum after opening " + inputPath;
                    } else {
                        _processForReport(spectrum, nucleus, undefined, true, false);
                        report = nucleus === "13C" ? _plainMultipletReport(spectrum, nucleus) : _plainMultipletReport(spectrum, nucleus);
                        referenceOffset = _referenceOffsetFromPeaks(spectrum, nucleus);
                        if (nucleus === "13C") {
                            _processForReport(spectrum, nucleus, 1, false, true);
                            peakReport = _plainPeakReport(spectrum, nucleus);
                        }
                        image = _exportSpectrumImage(spectrum, nucleus, imagePath);
                    }
                }
            } catch (taskError) {
                error = String(taskError);
            }

            if (!first) {
                json += ",\n";
            }
            first = false;
            json += "  \"" + _jsonEscape(compound + "|" + nucleus) + "\": {";
            json += "\"compound\": \"" + _jsonEscape(compound) + "\", ";
            json += "\"nucleus\": \"" + _jsonEscape(nucleus) + "\", ";
            json += "\"input\": \"" + _jsonEscape(inputPath) + "\", ";
            json += "\"report\": \"" + _jsonEscape(report) + "\", ";
            json += "\"peakReport\": \"" + _jsonEscape(peakReport) + "\", ";
            json += "\"image\": \"" + _jsonEscape(image) + "\", ";
            json += "\"mnova\": \"" + _jsonEscape(mnova) + "\", ";
            json += "\"referenceOffset\": \"" + _jsonEscape(referenceOffset) + "\", ";
            json += "\"error\": \"" + _jsonEscape(error) + "\"";
            json += "}";

            if (error) {
                _appendText(statusPath, "ERROR " + compound + " " + nucleus + ": " + error + "\n");
            } else {
                _appendText(statusPath, "OK " + compound + " " + nucleus + "\n");
            }
            dw.close();
        }

        _saveProcessedMnovaFiles(tasks, statusPath);

        json += "\n}\n";
        _writeText(outputJsonPath, json);
        _appendText(statusPath, "DONE\n");
    } catch (e) {
        _writeText(statusPath, "ERROR batch: " + e);
    }

    Application.quit();
}

function _importableNmrPath(path)
{
    var text = String(path);
    return text.replace(/\/fid$/i, "");
}

function _saveProcessedMnovaFiles(tasks, statusPath)
{
    var byCompound = {};
    var order = [];
    var i, task, key;

    for (i = 0; i < tasks.length; i++) {
        task = tasks[i];
        if (!task.mnovaPath) {
            continue;
        }
        key = task.compound;
        if (byCompound[key] === undefined) {
            byCompound[key] = [];
            order.push(key);
        }
        byCompound[key].push(task);
    }

    for (i = 0; i < order.length; i++) {
        key = order[i];
        _saveProcessedMnovaFile(key, byCompound[key], statusPath);
    }
}

function _saveProcessedMnovaFile(compound, tasks, statusPath)
{
    var mnovaPath = tasks.length ? tasks[0].mnovaPath : "";
    var doc, paths, i, nmrItems, spectrum, nucleus;

    if (!mnovaPath) {
        return;
    }

    try {
        _appendText(statusPath, "SAVE_MNOVA " + compound + " " + mnovaPath + "\n");
        doc = new Document();
        doc.newPage();
        Application.lockDocument(doc);

        paths = [];
        for (i = 0; i < tasks.length; i++) {
            paths.push(_importableNmrPath(tasks[i].inputPath));
        }
        serialization.importFile(paths, "", doc);

        nmrItems = doc.itemsByName("NMR Spectrum");
        for (i = 0; i < nmrItems.length && i < tasks.length; i++) {
            nucleus = tasks[i].nucleus;
            spectrum = new NMRSpectrum(nmrItems[i]);
            if (!spectrum.isValid()) {
                continue;
            }
            _processForReport(spectrum, nucleus, undefined, true, false);
            if (nucleus === "13C") {
                _processForReport(spectrum, nucleus, 1, false, true);
            }
            _prepareSpectrumForExport(spectrum, nucleus);
        }

        serialization.save(mnovaPath, "mnova");
        Application.unlockDocument(doc);
        _appendText(statusPath, "OK_MNOVA " + compound + "\n");
    } catch (e) {
        try {
            Application.unlockDocument(doc);
        } catch (unlockError) {
        }
        _appendText(statusPath, "ERROR_MNOVA " + compound + ": " + e + "\n");
    }
}

function dumpProcessingParameters(inputPath, outputPath, statusPath)
{
    try {
        _writeText(statusPath, "START dump input=" + inputPath + "\n");
        var dw = mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _writeText(statusPath, "ERROR: Could not open " + inputPath);
            Application.quit();
            return;
        }
        var spectrum = new NMRSpectrum(nmr.activeSpectrum());
        if (!spectrum.isValid()) {
            spectrum = new NMRSpectrum(mainWindow.activeDocument.getActiveItem("NMR Spectrum"));
        }
        var p = new NMRProcessing(spectrum.proc);
        var names = [
            "PP", "PP.Apply", "PP.Method", "PP.PeakType", "PP.peaktype",
            "PP.Positive", "PP.Negative", "PP.Threshold", "PP.threshold",
            "PP.Sensitivity", "PP.sensitivity", "PP.Global.Sensitivity",
            "PP.Global.Autosensitivity", "pp", "pp.apply", "pp.method",
            "pp.peaktype", "pp.threshold", "pp.sensitivity"
        ];
        var text = "";
        var i, name;
        for (i = 0; i < names.length; i++) {
            name = names[i];
            if (String(name).toLowerCase().indexOf("pp") >= 0 || String(name).toLowerCase().indexOf("peak") >= 0) {
                try {
                    text += name + "\t" + p.getParameter(name) + "\n";
                } catch (e) {
                    text += name + "\tERROR " + e + "\n";
                }
            }
        }
        _writeText(outputPath, text);
        _appendText(statusPath, "OK\n");
        dw.close();
    } catch (e) {
        _writeText(statusPath, "ERROR dump: " + e);
    }
    Application.quit();
}

function dumpSpectrumProperties(inputPath, outputPath, statusPath)
{
    try {
        _writeText(statusPath, "START properties input=" + inputPath + "\n");
        var dw = mainWindow.newWindow();
        if (!serialization.open(inputPath)) {
            _writeText(statusPath, "ERROR: Could not open " + inputPath);
            Application.quit();
            return;
        }
        var spectrum = new NMRSpectrum(nmr.activeSpectrum());
        if (!spectrum.isValid()) {
            spectrum = new NMRSpectrum(mainWindow.activeDocument.getActiveItem("NMR Spectrum"));
        }
        var names = [
            "integrals.show",
            "integrals.label.show",
            "integrals.label.position",
            "integrals.label.margin",
            "integrals.curve.show",
            "integrals.curve.margin",
            "integrals.curve.maxheight",
            "multiplets.integral.label.show",
            "multiplets.integral.curve.show",
            "axes.margin.mm"
        ];
        var text = "";
        var i, name;
        for (i = 0; i < names.length; i++) {
            name = names[i];
            try {
                text += name + "\t" + spectrum.getProperty(name) + "\n";
            } catch (e) {
                text += name + "\tERROR " + e + "\n";
            }
        }
        _writeText(outputPath, text);
        _appendText(statusPath, "OK\n");
        dw.close();
    } catch (e) {
        _writeText(statusPath, "ERROR properties: " + e);
    }
    Application.quit();
}
