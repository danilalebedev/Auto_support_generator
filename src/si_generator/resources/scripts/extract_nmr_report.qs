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

function _parseRenderSpec(text)
{
    if (!text || String(text).replace(/\s/g, "") === "") {
        return {};
    }
    try {
        if (typeof JSON !== "undefined" && JSON.parse) {
            return JSON.parse(text);
        }
    } catch (e) {
    }
    try {
        return eval("(" + text + ")");
    } catch (fallbackError) {
        return {};
    }
}

function _numberOrDefault(value, fallback)
{
    var parsed = Number(value);
    return isNaN(parsed) ? fallback : parsed;
}

function _xRange(nucleus, renderSpec)
{
    var range = renderSpec && renderSpec.x_range_ppm ? renderSpec.x_range_ppm : undefined;
    var fallback = nucleus === "13C" ? [-10.0, 210.0] : [-1.0, 12.0];
    if (range && range.length >= 2) {
        return [_numberOrDefault(range[0], fallback[0]), _numberOrDefault(range[1], fallback[1])];
    }
    return fallback;
}

function _targetSignalHeightFraction(renderSpec)
{
    var value = renderSpec ? _numberOrDefault(renderSpec.target_signal_height_fraction, 0.80) : 0.80;
    if (value < 0.20) {
        return 0.20;
    }
    if (value > 0.95) {
        return 0.95;
    }
    return value;
}

function _peakThresholdFraction(nucleus, renderSpec)
{
    var explicitValue = renderSpec && renderSpec.peak_threshold_fraction !== undefined ? Number(renderSpec.peak_threshold_fraction) : NaN;
    if (!isNaN(explicitValue)) {
        if (explicitValue < 0) {
            return 0;
        }
        if (explicitValue > 1) {
            return 1;
        }
        return explicitValue;
    }
    var policy = renderSpec && renderSpec.peak_picking ? String(renderSpec.peak_picking) : "normal";
    if (policy === "manual") {
        return 0;
    }
    if (policy === "minimal") {
        return nucleus === "1H" ? 0.08 : 0.03;
    }
    if (policy === "dense") {
        return nucleus === "1H" ? 0.025 : 0.01;
    }
    return nucleus === "1H" ? 0.05 : 0.018;
}

function _isIgnoredByRenderSpec(delta, renderSpec)
{
    var regions = renderSpec && renderSpec.ignore_regions_ppm ? renderSpec.ignore_regions_ppm : [];
    var i, region, left, right, minValue, maxValue;
    for (i = 0; i < regions.length; i++) {
        region = regions[i];
        if (!region || region.length < 2) {
            continue;
        }
        left = _numberOrDefault(region[0], delta);
        right = _numberOrDefault(region[1], delta);
        minValue = Math.min(left, right);
        maxValue = Math.max(left, right);
        if (delta >= minValue && delta <= maxValue) {
            return true;
        }
    }
    return false;
}

function _plainMultipletReport(spectrum, nucleus, renderSpec)
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

    return _filterMultipletReportByPeakThreshold(reporter.report(spectrum, false), spectrum, nucleus, renderSpec || {});
}

function _filterMultipletReportByPeakThreshold(report, spectrum, nucleus, renderSpec)
{
    var thresholdFraction = _peakThresholdFraction(nucleus, renderSpec || {});
    var bodyStart, header, body, trailingPeriod, segments, kept, peaks, maxIntensity, threshold, i, segment, bounds;

    if (!report || thresholdFraction <= 0) {
        return report;
    }

    peaks = _thresholdPeakData(spectrum, nucleus, renderSpec || {});
    maxIntensity = peaks.maxIntensity;
    if (maxIntensity <= 0) {
        return report;
    }
    threshold = maxIntensity * thresholdFraction;

    bodyStart = report.indexOf("\u03b4");
    if (bodyStart < 0) {
        return report;
    }

    header = report.substring(0, bodyStart + 1);
    body = report.substring(bodyStart + 1).replace(/^\s*=?\s*/, "");
    trailingPeriod = /\.\s*$/.test(body);
    body = body.replace(/\.\s*$/, "");
    segments = _splitSignalSegments(body);
    kept = [];

    for (i = 0; i < segments.length; i++) {
        segment = _trim(segments[i]);
        if (!segment) {
            continue;
        }
        bounds = _signalBounds(segment, nucleus);
        if (!bounds || _hasPeakAboveThreshold(peaks.values, bounds[0], bounds[1], threshold)) {
            kept.push(segment);
        }
    }

    if (!kept.length) {
        return report;
    }
    return header + " " + kept.join(", ") + (trailingPeriod ? "." : "");
}

function _thresholdPeakData(spectrum, nucleus, renderSpec)
{
    var peaks, peak, i, values, delta, intensity, maxIntensity;
    values = [];
    maxIntensity = 0;

    try {
        peaks = new Peaks(spectrum.peaks());
        if (!peaks || !peaks.count) {
            peaks = new Peaks(spectrum, _visibleRegion(nucleus, renderSpec || {}));
        }
        for (i = 0; i < peaks.count; i++) {
            peak = peaks.at(i);
            delta = peak.delta();
            if (_isIgnoredImagePeak(spectrum, nucleus, peak, renderSpec || {})) {
                continue;
            }
            intensity = Math.abs(peak.intensity);
            values.push({delta: delta, intensity: intensity});
            if (intensity > maxIntensity) {
                maxIntensity = intensity;
            }
        }
    } catch (e) {
    }

    return {values: values, maxIntensity: maxIntensity};
}

function _hasPeakAboveThreshold(peaks, left, right, threshold)
{
    var i, peak;
    for (i = 0; i < peaks.length; i++) {
        peak = peaks[i];
        if (peak.delta >= left && peak.delta <= right && peak.intensity >= threshold) {
            return true;
        }
    }
    return false;
}

function _signalBounds(segment, nucleus)
{
    var match, a, b, tolerance;
    match = segment.match(/^\s*(-?\d+(?:\.\d+)?)\s*(?:[-\u2013]\s*(-?\d+(?:\.\d+)?))?/);
    if (!match) {
        return null;
    }
    a = Number(match[1]);
    b = match[2] !== undefined ? Number(match[2]) : a;
    if (isNaN(a) || isNaN(b)) {
        return null;
    }
    tolerance = nucleus === "13C" ? 0.18 : 0.04;
    return [Math.min(a, b) - tolerance, Math.max(a, b) + tolerance];
}

function _splitSignalSegments(body)
{
    var result, current, depth, i, ch;
    result = [];
    current = "";
    depth = 0;
    for (i = 0; i < body.length; i++) {
        ch = body.charAt(i);
        if (ch === "(") {
            depth++;
        } else if (ch === ")" && depth > 0) {
            depth--;
        }
        if (ch === "," && depth === 0) {
            result.push(current);
            current = "";
        } else {
            current += ch;
        }
    }
    result.push(current);
    return result;
}

function _trim(value)
{
    return String(value).replace(/^\s+|\s+$/g, "");
}

function _referenceValue(spectrum, nucleus)
{
    var solvent = String(spectrum.solvent || "").toLowerCase();
    if (solvent.indexOf("dmso") >= 0) {
        return nucleus === "13C" ? 39.52 : 2.50;
    }
    return nucleus === "13C" ? 77.16 : 7.26;
}

function _referenceSpectrum(spectrum, nucleus, renderSpec)
{
    var reference = _referenceValue(spectrum, nucleus);
    var tolerance = nucleus === "13C" ? 2.0 : 0.20;
    var label = _highlightSolventPeaks(renderSpec || {}) ? "CHCl3 reference" : "";

    try {
        spectrum.reference(1, reference, reference, true, tolerance, label);
        if (!_highlightSolventPeaks(renderSpec || {})) {
            _hideSolventPeakAnnotations(spectrum);
        }
        spectrum.update();
    } catch (e) {
        // Referencing is best-effort: if Mnova cannot find CHCl3/CDCl3, keep the
        // spectrum usable and report the unreferenced peak list.
    }
}

function _baselineMode(renderSpec)
{
    var mode = renderSpec && renderSpec.baseline_mode !== undefined ? String(renderSpec.baseline_mode).toLowerCase() : "auto";
    if (mode === "off" || mode === "bernstein" || mode === "whittaker") {
        return mode;
    }
    return "auto";
}

function _baselineApply(nucleus, renderSpec)
{
    if (renderSpec && renderSpec.baseline_apply !== undefined) {
        return Boolean(renderSpec.baseline_apply);
    }
    return nucleus === "13C";
}

function _positiveBaselineInt(value, fallback)
{
    var parsed = parseInt(value, 10);
    if (isNaN(parsed) || parsed <= 0) {
        return fallback;
    }
    return parsed;
}

function _positiveBaselineNumber(value, fallback)
{
    var parsed = Number(value);
    if (isNaN(parsed) || parsed <= 0) {
        return fallback;
    }
    return parsed;
}

function _appendBaselineWarning(statusPath, message)
{
    if (statusPath) {
        _appendText(statusPath, "WARNING baseline " + message + "\n");
    }
}

function _setBaselineParameter(processing, name, value, statusPath, context)
{
    try {
        processing.setParameter(name, value);
        return true;
    } catch (e) {
        if (statusPath) {
            _appendText(statusPath, "WARNING baseline parameter " + name + " not applied for " + context + ": " + e + "\n");
        }
        return false;
    }
}

function _setAnyBaselineParameter(processing, names, value, statusPath, context)
{
    var i, errors = [];
    for (i = 0; i < names.length; i++) {
        try {
            processing.setParameter(names[i], value);
            return true;
        } catch (e) {
            errors.push(names[i] + "=" + e);
        }
    }
    _appendBaselineWarning(statusPath, "parameter not applied for " + context + ": " + names.join("/") + " (" + errors.join("; ") + ")");
    return false;
}

function _configureBaselineProcessing(processing, nucleus, renderSpec, statusPath)
{
    var mode = _baselineMode(renderSpec || {});
    var context = nucleus + " " + mode;
    var lambdaValue, asymmetryValue, polyOrder;

    if (!_baselineApply(nucleus, renderSpec || {}) || mode === "off") {
        if (statusPath) {
            _appendText(statusPath, "BASELINE " + nucleus + " mode=" + mode + " apply=false\n");
        }
        return false;
    }

    _setBaselineParameter(processing, "BC.Apply", true, statusPath, context);
    if (mode === "whittaker") {
        lambdaValue = _positiveBaselineNumber(renderSpec ? renderSpec.whittaker_lambda : undefined, 100000);
        asymmetryValue = _positiveBaselineNumber(renderSpec ? renderSpec.whittaker_asymmetry : undefined, 0.001);
        _setBaselineParameter(processing, "BC.algorithm", "Whittaker", statusPath, context);
        _setAnyBaselineParameter(
            processing,
            ["BC.Whittaker.Lambda", "BC.whittaker.lambda", "BC.Lambda", "BC.lambda"],
            lambdaValue,
            statusPath,
            context + " lambda"
        );
        _setAnyBaselineParameter(
            processing,
            ["BC.Whittaker.Asymmetry", "BC.whittaker.asymmetry", "BC.Asymmetry", "BC.asymmetry"],
            asymmetryValue,
            statusPath,
            context + " asymmetry"
        );
        if (statusPath) {
            _appendText(statusPath, "BASELINE " + nucleus + " mode=whittaker apply=true lambda=" + lambdaValue + " asymmetry=" + asymmetryValue + "\n");
        }
        return true;
    }

    polyOrder = _positiveBaselineInt(renderSpec ? renderSpec.baseline_poly_order : undefined, 3);
    _setBaselineParameter(processing, "BC.algorithm", "Bernstein", statusPath, context);
    _setBaselineParameter(
        processing,
        "BC.PolyOrder",
        polyOrder,
        statusPath,
        context + " poly_order"
    );
    if (statusPath) {
        _appendText(statusPath, "BASELINE " + nucleus + " mode=bernstein apply=true poly_order=" + polyOrder + "\n");
    }
    return true;
}

function _annotationRange(annotation, isIntegral)
{
    var left, right;
    try {
        if (isIntegral) {
            left = Number(annotation.rangeMin(1));
            right = Number(annotation.rangeMax(1));
        } else {
            left = Number(annotation.rangeMin);
            right = Number(annotation.rangeMax);
        }
    } catch (e) {
        return null;
    }
    if (isNaN(left) || isNaN(right)) {
        return null;
    }
    return [Math.min(left, right), Math.max(left, right)];
}

function _excludedProtonAnnotation(spectrum, annotation, isIntegral, renderSpec)
{
    var range = _annotationRange(annotation, isIntegral);
    var center, solvent, reference, excluded, i;
    if (!range) {
        return false;
    }
    center = (range[0] + range[1]) / 2;
    if (_isIgnoredByRenderSpec(center, renderSpec || {})) {
        return true;
    }
    solvent = String(spectrum.solvent || "").toLowerCase();
    reference = solvent.indexOf("dmso") >= 0 ? 2.50 : 7.26;
    excluded = [reference];
    if (solvent.indexOf("dmso") >= 0) {
        excluded.push(3.33);
    } else {
        excluded.push(1.56);
        excluded.push(1.77);
    }
    for (i = 0; i < excluded.length; i++) {
        if (excluded[i] >= range[0] - 0.02 && excluded[i] <= range[1] + 0.02) {
            return true;
        }
    }
    return false;
}

function _normalizeAnnotationListToHydrogenCount(spectrum, list, expectedHydrogens, isIntegral, renderSpec, forceNormalization)
{
    var total = 0;
    var currentTotal = 0;
    var deviation, annotation, value, i;
    var entries = [];
    if (!list || !list.count || expectedHydrogens <= 0) {
        return false;
    }
    for (i = 0; i < list.count; i++) {
        annotation = list.at(i);
        if (_excludedProtonAnnotation(spectrum, annotation, isIntegral, renderSpec || {})) {
            continue;
        }
        try {
            value = Number(annotation.integralValue(1.0));
        } catch (e) {
            value = 0;
        }
        if (!isNaN(value) && value > 0) {
            total += value;
            entries.push({annotation: annotation, value: value, assigned: 0, scaled: 0});
            if (!isIntegral && Number(annotation.nH) > 0) {
                currentTotal += Number(annotation.nH);
            }
        }
    }
    if (total <= 0) {
        return false;
    }
    if (isIntegral || currentTotal <= 0) {
        currentTotal = Number(list.normValue) > 0 ? total / Number(list.normValue) : 0;
    }
    deviation = currentTotal > 0 ? Math.abs(currentTotal - expectedHydrogens) / expectedHydrogens : 1;
    if (!forceNormalization && deviation < 0.15) {
        return false;
    }
    list.normValue = total / expectedHydrogens;
    if (!isIntegral && expectedHydrogens >= entries.length) {
        _assignMultipletHydrogens(entries, expectedHydrogens, total);
    }
    return true;
}

function _assignMultipletHydrogens(entries, expectedHydrogens, total)
{
    var assignedTotal = 0;
    var i, bestIndex, bestScore;
    for (i = 0; i < entries.length; i++) {
        entries[i].scaled = entries[i].value * expectedHydrogens / total;
        entries[i].assigned = Math.max(1, Math.floor(entries[i].scaled));
        assignedTotal += entries[i].assigned;
    }
    while (assignedTotal < expectedHydrogens) {
        bestIndex = -1;
        bestScore = -Infinity;
        for (i = 0; i < entries.length; i++) {
            if (entries[i].scaled - entries[i].assigned > bestScore) {
                bestScore = entries[i].scaled - entries[i].assigned;
                bestIndex = i;
            }
        }
        if (bestIndex < 0) {
            break;
        }
        entries[bestIndex].assigned++;
        assignedTotal++;
    }
    while (assignedTotal > expectedHydrogens) {
        bestIndex = -1;
        bestScore = -Infinity;
        for (i = 0; i < entries.length; i++) {
            if (entries[i].assigned > 1 && entries[i].assigned - entries[i].scaled > bestScore) {
                bestScore = entries[i].assigned - entries[i].scaled;
                bestIndex = i;
            }
        }
        if (bestIndex < 0) {
            break;
        }
        entries[bestIndex].assigned--;
        assignedTotal--;
    }
    for (i = 0; i < entries.length; i++) {
        entries[i].annotation.nH = entries[i].assigned;
    }
}

function _normalizeProtonIntegrals(spectrum, renderSpec, statusPath)
{
    var expectedHydrogens = Number(renderSpec ? renderSpec.expected_hydrogen_count : 0);
    var multiplets, integrals, multipletsChanged, integralsChanged;
    if (!expectedHydrogens || expectedHydrogens <= 0) {
        return;
    }
    try {
        multiplets = new Multiplets(spectrum.multiplets());
        multipletsChanged = _normalizeAnnotationListToHydrogenCount(
            spectrum, multiplets, expectedHydrogens, false, renderSpec || {}, false
        );
        if (multipletsChanged) {
            spectrum.setMultiplets(multiplets);
        }
    } catch (multipletError) {
        if (statusPath) {
            _appendText(statusPath, "WARNING proton multiplet normalization failed: " + multipletError + "\n");
        }
    }
    try {
        integrals = new Integrals(spectrum.integrals());
        integralsChanged = _normalizeAnnotationListToHydrogenCount(
            spectrum, integrals, expectedHydrogens, true, renderSpec || {}, false
        );
        if (integralsChanged) {
            spectrum.setIntegrals(integrals);
        }
    } catch (integralError) {
        if (statusPath) {
            _appendText(statusPath, "WARNING proton integral normalization failed: " + integralError + "\n");
        }
    }
    if (multipletsChanged && !integralsChanged && integrals) {
        integralsChanged = _normalizeAnnotationListToHydrogenCount(
            spectrum, integrals, expectedHydrogens, true, renderSpec || {}, true
        );
        if (integralsChanged) {
            spectrum.setIntegrals(integrals);
        }
    } else if (integralsChanged && !multipletsChanged && multiplets) {
        multipletsChanged = _normalizeAnnotationListToHydrogenCount(
            spectrum, multiplets, expectedHydrogens, false, renderSpec || {}, true
        );
        if (multipletsChanged) {
            spectrum.setMultiplets(multiplets);
        }
    }
    if (multipletsChanged || integralsChanged) {
        spectrum.process();
        spectrum.update();
        if (statusPath) {
            _appendText(statusPath, "INTEGRAL_NORMALIZATION 1H target=" + expectedHydrogens + " multiplets=" + Boolean(multipletsChanged) + " integrals=" + Boolean(integralsChanged) + "\n");
        }
    }
}

function _processForReport(spectrum, nucleus, sensitivity, doReference, peakOnlyPass, renderSpec, statusPath)
{
    var p = new NMRProcessing(spectrum.proc);

    if (doReference) {
        _referenceSpectrum(spectrum, nucleus, renderSpec || {});
    }

    _configureBaselineProcessing(p, nucleus, renderSpec || {}, statusPath);
    p.setParameter("PP.Apply", false);
    p.setParameter("PP.Method", "GSD");
    if (nucleus === "13C" && sensitivity !== undefined) {
        p.setParameter("PP.Sensitivity", sensitivity);
    }
    spectrum.process(p);

    p.setParameter("Mult.Apply", false);
    p.setParameter("integration.apply", false);
    spectrum.process(p);

    if (nucleus === "13C" && peakOnlyPass) {
        _clearNonPeakAnnotations(spectrum);
        spectrum.update();
        return;
    }

    p.setParameter("integration.method", "Auto");
    p.setParameter("integration.apply", true);
    p.setParameter("Mult.Apply", true);
    spectrum.process(p);
    if (nucleus === "1H") {
        _normalizeProtonIntegrals(spectrum, renderSpec || {}, statusPath);
    }
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

function _visibleRegion(nucleus, renderSpec)
{
    var range = _xRange(nucleus, renderSpec || {});
    return new SpectrumRegion(range[0], range[1]);
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

function _highlightSolventPeaks(renderSpec)
{
    if (renderSpec && renderSpec.highlight_solvent_peaks !== undefined) {
        return Boolean(renderSpec.highlight_solvent_peaks);
    }
    return false;
}

function _hideSolventPeakAnnotations(spectrum)
{
    try {
        spectrum.setProperty("peaks.showAnnotations", false);
        spectrum.setProperty("peaks.showAssignments", false);
    } catch (e) {
    }
}

function _peakText(peak)
{
    var parts = [];
    var names = ["annotation", "label", "name", "comment", "assignment", "solvent"];
    var i, name, value;
    if (peak === undefined || peak === null) {
        return "";
    }
    for (i = 0; i < names.length; i++) {
        name = names[i];
        try {
            value = peak[name];
            if (value !== undefined && value !== null) {
                parts.push(String(value));
            }
        } catch (e) {
        }
        try {
            if (peak[name] !== undefined && typeof peak[name] === "function") {
                value = peak[name]();
                if (value !== undefined && value !== null) {
                    parts.push(String(value));
                }
            }
        } catch (e2) {
        }
    }
    try {
        parts.push(String(peak));
    } catch (e3) {
    }
    return parts.join(" ").toLowerCase();
}

function _isSolventPeak(spectrum, nucleus, peak, delta)
{
    var text = _peakText(peak);
    var solvent = String(spectrum.solvent || "").toLowerCase();
    if (
        text.indexOf("cdcl3") >= 0 ||
        text.indexOf("chcl3") >= 0 ||
        text.indexOf("chloroform") >= 0 ||
        text.indexOf("dmso") >= 0 ||
        text.indexOf("h2o") >= 0 ||
        text.indexOf("water") >= 0 ||
        text.indexOf("solvent") >= 0
    ) {
        return true;
    }
    if (nucleus === "13C" && solvent.indexOf("cdcl") >= 0 && delta >= 76.0 && delta <= 78.2) {
        return true;
    }
    if (nucleus === "13C" && solvent.indexOf("dmso") >= 0 && delta >= 38.8 && delta <= 40.2) {
        return true;
    }
    return _isReferencePeak(spectrum, nucleus, delta);
}

function _isIgnoredImagePeak(spectrum, nucleus, peak, renderSpec)
{
    var delta = peak.delta();
    if (_isIgnoredByRenderSpec(delta, renderSpec || {})) {
        return true;
    }
    if (!_highlightSolventPeaks(renderSpec || {}) && _isSolventPeak(spectrum, nucleus, peak, delta)) {
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

function _filterPeaksForImage(spectrum, nucleus, renderSpec)
{
    var allPeaks, keptPeaks, peak, i, intensity, maxIntensity, threshold;

    try {
        allPeaks = new Peaks(spectrum.peaks());
        if (!allPeaks || !allPeaks.count) {
            allPeaks = new Peaks(spectrum, _visibleRegion(nucleus, renderSpec));
        }
        maxIntensity = 0;
        for (i = 0; i < allPeaks.count; i++) {
            peak = allPeaks.at(i);
            if (_isIgnoredImagePeak(spectrum, nucleus, peak, renderSpec)) {
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
                if (_isIgnoredImagePeak(spectrum, nucleus, peak, renderSpec)) {
                    continue;
                }
                intensity = Math.abs(peak.intensity);
                if (intensity > maxIntensity) {
                    maxIntensity = intensity;
                }
            }
        }
        threshold = maxIntensity * _peakThresholdFraction(nucleus, renderSpec || {});
        keptPeaks = new Peaks();
        for (i = 0; i < allPeaks.count; i++) {
            peak = allPeaks.at(i);
            if (!_isIgnoredImagePeak(spectrum, nucleus, peak, renderSpec) && Math.abs(peak.intensity) >= threshold) {
                if (nucleus === "1H") {
                    peak.annotation = "";
                }
                keptPeaks.append(peak);
            }
        }
        spectrum.setPeaks(keptPeaks);
        if (!_highlightSolventPeaks(renderSpec || {})) {
            _hideSolventPeakAnnotations(spectrum);
        }
    } catch (e) {
    }
}

function _fitVerticalScaleForImage(spectrum, nucleus, renderSpec)
{
    var peaks, peak, i, intensity, maxIntensity, minIntensity, top, bottom, targetHeight;

    try {
        peaks = new Peaks(spectrum, _visibleRegion(nucleus, renderSpec));
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
            targetHeight = _targetSignalHeightFraction(renderSpec || {});
            top = maxIntensity / targetHeight;
            bottom = nucleus === "1H" ? -maxIntensity * 0.14 : (minIntensity < 0 ? minIntensity * 1.15 : -maxIntensity * 0.03);
            spectrum.vertZoom(bottom, top);
        }
    } catch (e) {
    }
}

function _plainPeakReport(spectrum, nucleus, renderSpec)
{
    var peaks, peak, i, delta, values, solvent, frequency, header, precision, range, intensity, maxIntensity, threshold;
    range = _xRange(nucleus, renderSpec || {});
    var minDelta = range[0];
    var maxDelta = range[1];
    var solventReference = _referenceValue(spectrum, nucleus);
    var solventTolerance = nucleus === "13C" ? 0.35 : 0.04;

    peaks = new Peaks(spectrum, new SpectrumRegion(minDelta, maxDelta));
    if (!peaks || !peaks.count) {
        peaks = new Peaks(spectrum.peaks());
    }
    peaks.sort(false);

    values = [];
    maxIntensity = 0;
    precision = nucleus === "13C" ? 1 : 2;
    for (i = 0; i < peaks.count; i++) {
        peak = peaks.at(i);
        delta = peak.delta();
        if (nucleus === "13C" && _isSolventPeak(spectrum, nucleus, peak, delta)) {
            continue;
        }
        if (delta < minDelta || delta > maxDelta || _isIgnoredByRenderSpec(delta, renderSpec || {})) {
            continue;
        }
        intensity = Math.abs(peak.intensity);
        if (intensity > maxIntensity) {
            maxIntensity = intensity;
        }
    }
    threshold = maxIntensity * _peakThresholdFraction(nucleus, renderSpec || {});
    for (i = 0; i < peaks.count; i++) {
        peak = peaks.at(i);
        delta = peak.delta();
        if (nucleus === "13C" && _isSolventPeak(spectrum, nucleus, peak, delta)) {
            continue;
        }
        if (delta < minDelta || delta > maxDelta || _isIgnoredByRenderSpec(delta, renderSpec || {})) {
            continue;
        }
        if (threshold > 0 && Math.abs(peak.intensity) < threshold) {
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

function _readMNGPSpectrumProperties(profilePath, statusPath)
{
    var file = new File(profilePath);
    if (!file.open(File.ReadOnly)) {
        throw "Could not open .mngp file: " + profilePath;
    }

    var stream = new BinaryStream(file);
    stream.endianness = BinaryStream.eBig;
    var header = stream.readString();
    if (header !== "MestReNova Graphic Properties") {
        file.close();
        throw "Unsupported .mngp header: " + header;
    }

    stream.readInt32();
    stream.readInt32();
    stream.readInt32();
    stream.readInt32();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readReal64();
    stream.readInt8();

    var payloadSize = stream.readInt32();
    if (payloadSize <= 0 || payloadSize > 10000000) {
        file.close();
        throw "Invalid .mngp payload size: " + payloadSize;
    }
    var payload = stream.readBytes(payloadSize);
    file.close();
    _appendText(statusPath, "GRAPHICS_PROFILE payload_size=" + payloadSize + " path=" + profilePath + "\n");
    return payload;
}

function _applyGraphicsProfileDefault(graphicsProfilePath, statusPath)
{
    if (!graphicsProfilePath) {
        return false;
    }
    try {
        var payload = _readMNGPSpectrumProperties(graphicsProfilePath, statusPath);
        var nmrSettings = new Settings("NMR");
        nmrSettings.setValue("Spectrum Properties", payload);
        _appendText(statusPath, "GRAPHICS_PROFILE settings=NMR/Spectrum Properties path=" + graphicsProfilePath + "\n");
        return true;
    } catch (e) {
        _appendText(statusPath, "WARNING graphics profile not applied: " + e + " path=" + graphicsProfilePath + "\n");
        return false;
    }
}

function _exportSpectrumImage(spectrum, nucleus, imagePath, renderSpec, graphicsProfilePath, statusPath)
{
    if (!imagePath) {
        return "";
    }

    try {
        if (_isTwoDimensionalNucleus(nucleus)) {
            _prepareTwoDimensionalSpectrumForExport(spectrum, nucleus, renderSpec || {}, statusPath);
        } else {
            _prepareSpectrumForExport(spectrum, nucleus, renderSpec || {}, graphicsProfilePath || "", statusPath);
        }
        return _exportCurrentPageImage(imagePath);
    } catch (e) {
        return "";
    }
}

function _exportCurrentPageImage(imagePath)
{
    if (!imagePath) {
        return "";
    }
    mainWindow.activeWindow().update();
    var page = mainWindow.activeDocument.curPage();
    var pixmap = draw.toPixmap(page, 300);
    pixmap.save(imagePath, "PNG");
    return imagePath;
}

function _isTwoDimensionalNucleus(nucleus)
{
    return nucleus === "HSQC" || nucleus === "HMBC" || nucleus === "NOESY" || nucleus === "COSY" || nucleus === "TOCSY" || nucleus === "ROESY" || nucleus === "2D";
}

function _setSpectrumProperty(spectrum, propertyName, value, statusPath)
{
    try {
        spectrum.setProperty(propertyName, value);
        return true;
    } catch (e) {
        _appendText(statusPath, "WARNING 2D property not applied: " + propertyName + " (" + e + ")\n");
        return false;
    }
}

function _twoDimensionalContourScaling(renderSpec)
{
    var value = renderSpec && renderSpec.contour_scaling !== undefined ? Number(renderSpec.contour_scaling) : 4.0;
    if (isNaN(value) || value < 0.1) {
        return 4.0;
    }
    if (value > 100) {
        return 100;
    }
    return value;
}

function _twoDimensionalTraceSize(renderSpec, orientation)
{
    var key = orientation === "vertical" ? "vertical_trace_size" : "horizontal_trace_size";
    var value = renderSpec && renderSpec[key] !== undefined ? Number(renderSpec[key]) : 0.08;
    if (isNaN(value) || value < 0.005) {
        return 0.08;
    }
    if (value > 0.25) {
        return 0.25;
    }
    return value;
}

function _prepareTwoDimensionalSpectrumForExport(spectrum, nucleus, renderSpec, statusPath)
{
    var contourScaling = _twoDimensionalContourScaling(renderSpec || {});
    var horizontalTraceSize = _twoDimensionalTraceSize(renderSpec || {}, "horizontal");
    var verticalTraceSize = _twoDimensionalTraceSize(renderSpec || {}, "vertical");

    _setSpectrumProperty(spectrum, "traces.horizontal.isExternal", false, statusPath);
    _setSpectrumProperty(spectrum, "traces.vertical.isExternal", false, statusPath);
    _setSpectrumProperty(spectrum, "traces.horizontal.type", "Proj", statusPath);
    _setSpectrumProperty(spectrum, "traces.vertical.type", "Proj", statusPath);
    _setSpectrumProperty(spectrum, "traces.horizontal.visible", true, statusPath);
    _setSpectrumProperty(spectrum, "traces.vertical.visible", true, statusPath);
    _setSpectrumProperty(spectrum, "traces.same_size", false, statusPath);
    _setSpectrumProperty(spectrum, "traces.horizontal.size", horizontalTraceSize, statusPath);
    _setSpectrumProperty(spectrum, "traces.vertical.size", verticalTraceSize, statusPath);
    _setSpectrumProperty(spectrum, "contours.scaling", contourScaling, statusPath);
    _setSpectrumProperty(spectrum, "grid.showtracesframe", false, statusPath);
    _setSpectrumProperty(spectrum, "axes.horizontal.visible", true, statusPath);
    _setSpectrumProperty(spectrum, "axes.vertical.visible", true, statusPath);
    _setSpectrumProperty(spectrum, "axes.horizontal.units", "ppm", statusPath);
    _setSpectrumProperty(spectrum, "axes.vertical.units", "ppm", statusPath);
    _setSpectrumProperty(spectrum, "axes.horizontal.showlabel", true, statusPath);
    _setSpectrumProperty(spectrum, "axes.vertical.showlabel", true, statusPath);
    _setSpectrumProperty(spectrum, "axes.horizontal.label", "1H / ppm", statusPath);
    _setSpectrumProperty(spectrum, "axes.vertical.label", _twoDimensionalVerticalNucleus(nucleus) + " / ppm", statusPath);
    try {
        spectrum.updateTraces();
    } catch (e) {
        _appendText(statusPath, "WARNING 2D traces not updated: " + e + "\n");
    }
    spectrum.update();
    _appendText(statusPath, "2D_TRACES " + nucleus + " horizontal=Proj vertical=Proj horizontal_size=" + horizontalTraceSize + " vertical_size=" + verticalTraceSize + " contour_scaling=" + contourScaling + "\n");
}

function _twoDimensionalVerticalNucleus(nucleus)
{
    return nucleus === "NOESY" || nucleus === "COSY" || nucleus === "TOCSY" || nucleus === "ROESY" ? "1H" : "13C";
}

function _traceRenderSpec(renderSpec, orientation)
{
    var key = orientation === "vertical" ? "vertical_trace_render_spec" : "horizontal_trace_render_spec";
    return renderSpec && renderSpec[key] ? renderSpec[key] : {};
}

function _importAndPrepareTrace(path, nucleus, renderSpec, statusPath)
{
    if (!path) {
        return undefined;
    }
    var doc = mainWindow.activeDocument;
    doc.newPage(true);
    serialization.importFile(_importableNmrPath(path), "", doc);
    var trace = new NMRSpectrum(nmr.activeSpectrum());
    if (!trace.isValid()) {
        throw "No imported " + nucleus + " trace spectrum from " + path;
    }
    _processForReport(trace, nucleus, undefined, true, false, renderSpec || {}, statusPath);
    _prepareSpectrumForExport(trace, nucleus, renderSpec || {}, "", statusPath);
    return trace;
}

function _attachTraceSpectra(spectrum, horizontalTrace, verticalTrace, statusPath)
{
    if (horizontalTrace && horizontalTrace.isValid()) {
        spectrum.setTrace(horizontalTrace, true);
        _setSpectrumProperty(spectrum, "traces.horizontal.visible", true, statusPath);
    }
    if (verticalTrace && verticalTrace.isValid()) {
        spectrum.setTrace(verticalTrace, false);
        _setSpectrumProperty(spectrum, "traces.vertical.visible", true, statusPath);
    }
    _setSpectrumProperty(spectrum, "traces.same_size", false, statusPath);
    spectrum.update();
}

function _attachExternalTraces(spectrum, nucleus, horizontalTracePath, verticalTracePath, renderSpec, statusPath)
{
    if (!horizontalTracePath && !verticalTracePath) {
        return false;
    }
    var doc = mainWindow.activeDocument;
    var spectrumPage = doc.curPage();
    var horizontalTrace = _importAndPrepareTrace(
        horizontalTracePath,
        "1H",
        _traceRenderSpec(renderSpec || {}, "horizontal"),
        statusPath
    );
    var verticalTrace;
    if (verticalTracePath && verticalTracePath === horizontalTracePath && horizontalTrace) {
        verticalTrace = horizontalTrace;
    } else {
        verticalTrace = _importAndPrepareTrace(
            verticalTracePath,
            _twoDimensionalVerticalNucleus(nucleus),
            _traceRenderSpec(renderSpec || {}, "vertical"),
            statusPath
        );
    }
    doc.setCurPage(spectrumPage);
    doc.setActiveItem(spectrum);
    _attachTraceSpectra(spectrum, horizontalTrace, verticalTrace, statusPath);
    _appendText(statusPath, "2D_EXTERNAL_TRACES " + nucleus + " horizontal=" + (horizontalTracePath || "none") + " vertical=" + (verticalTracePath || "none") + "\n");
    return true;
}

function _prepareSpectrumForExport(spectrum, nucleus, renderSpec, graphicsProfilePath, statusPath)
{
    var range = _xRange(nucleus, renderSpec || {});
    _referenceSpectrum(spectrum, nucleus, renderSpec || {});
    if (nucleus === "13C") {
        _clearNonPeakAnnotations(spectrum);
    } else {
        _hideProtonImageClutter(spectrum);
    }
    spectrum.horzZoom(range[0], range[1]);
    _fitVerticalScaleForImage(spectrum, nucleus, renderSpec || {});
    _filterPeaksForImage(spectrum, nucleus, renderSpec || {});
    spectrum.update();
}

function _spectrumReport(spectrum, nucleus, renderSpec)
{
    if (nucleus === "13C") {
        return _plainPeakReport(spectrum, nucleus, renderSpec || {});
    }
    return _plainMultipletReport(spectrum, nucleus, renderSpec || {});
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

        _processForReport(spectrum, nucleus, undefined, true, false, {}, statusPath);
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
            var renderSpec = parts.length >= 6 ? _parseRenderSpec(parts[5]) : {};
            var singleMnovaPath = parts.length >= 7 ? parts[6] : "";
            var graphicsProfilePath = parts.length >= 8 ? parts[7] : "";
            var horizontalTracePath = parts.length >= 9 ? parts[8] : "";
            var verticalTracePath = parts.length >= 10 ? parts[9] : "";
            tasks.push({compound: compound, nucleus: nucleus, inputPath: inputPath, imagePath: imagePath, mnovaPath: mnovaPath, renderSpec: renderSpec, singleMnovaPath: singleMnovaPath, graphicsProfilePath: graphicsProfilePath, horizontalTracePath: horizontalTracePath, verticalTracePath: verticalTracePath});
            _appendText(statusPath, "TASK " + compound + " " + nucleus + " " + inputPath + "\n");

            var dw = mainWindow.newWindow();
            var report = "";
            var peakReport = "";
            var image = "";
            var mnova = mnovaPath;
            var singleMnova = "";
            var referenceOffset = 0;
            var error = "";

            try {
                _applyGraphicsProfileDefault(graphicsProfilePath, statusPath);
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
                        if (_isTwoDimensionalNucleus(nucleus)) {
                            _prepareTwoDimensionalSpectrumForExport(spectrum, nucleus, renderSpec || {}, statusPath);
                            _attachExternalTraces(spectrum, nucleus, horizontalTracePath, verticalTracePath, renderSpec || {}, statusPath);
                            image = _exportCurrentPageImage(imagePath);
                            singleMnova = _saveSingleProcessedMnovaFile(compound, nucleus, spectrum, singleMnovaPath, renderSpec, graphicsProfilePath, statusPath, true);
                        } else {
                            _processForReport(spectrum, nucleus, undefined, true, false, renderSpec, statusPath);
                            report = _spectrumReport(spectrum, nucleus, renderSpec);
                            referenceOffset = _referenceOffsetFromPeaks(spectrum, nucleus);
                            if (nucleus === "13C") {
                                _processForReport(spectrum, nucleus, 1, false, true, renderSpec, statusPath);
                                peakReport = _plainPeakReport(spectrum, nucleus, renderSpec);
                            }
                            image = _exportSpectrumImage(spectrum, nucleus, imagePath, renderSpec, graphicsProfilePath, statusPath);
                            singleMnova = _saveSingleProcessedMnovaFile(compound, nucleus, spectrum, singleMnovaPath, renderSpec, graphicsProfilePath, statusPath, false);
                        }
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
            json += "\"singleMnova\": \"" + _jsonEscape(singleMnova) + "\", ";
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

function _saveSingleProcessedMnovaFile(compound, nucleus, spectrum, singleMnovaPath, renderSpec, graphicsProfilePath, statusPath, prepared)
{
    if (!singleMnovaPath) {
        return "";
    }

    try {
        _appendText(statusPath, "SAVE_SINGLE_MNOVA " + compound + " " + nucleus + " " + singleMnovaPath + "\n");
        if (!prepared) {
            if (_isTwoDimensionalNucleus(nucleus)) {
                _prepareTwoDimensionalSpectrumForExport(spectrum, nucleus, renderSpec || {}, statusPath);
            } else {
                _prepareSpectrumForExport(spectrum, nucleus, renderSpec || {}, graphicsProfilePath || "", statusPath);
            }
        }
        mainWindow.activeWindow().update();
        serialization.save(singleMnovaPath, "mnova");
        _appendText(statusPath, "OK_SINGLE_MNOVA " + compound + " " + nucleus + "\n");
        return singleMnovaPath;
    } catch (e) {
        _appendText(statusPath, "ERROR_SINGLE_MNOVA " + compound + " " + nucleus + ": " + e + "\n");
        return "";
    }
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
    var doc, i, nmrItems, spectrum, nucleus, spectraByTask, spectraByNucleus, verticalNucleus;

    if (!mnovaPath) {
        return;
    }

    try {
        _appendText(statusPath, "SAVE_MNOVA " + compound + " " + mnovaPath + "\n");
        doc = new Document();
        doc.newPage();
        Application.lockDocument(doc);

        for (i = 0; i < tasks.length; i++) {
            _applyGraphicsProfileDefault(tasks[i].graphicsProfilePath || "", statusPath);
            serialization.importFile(_importableNmrPath(tasks[i].inputPath), "", doc);
        }

        nmrItems = doc.itemsByName("NMR Spectrum");
        spectraByTask = [];
        spectraByNucleus = {};
        for (i = 0; i < nmrItems.length && i < tasks.length; i++) {
            nucleus = tasks[i].nucleus;
            spectrum = new NMRSpectrum(nmrItems[i]);
            spectraByTask.push(spectrum);
            if (!spectrum.isValid()) {
                continue;
            }
            if (!_isTwoDimensionalNucleus(nucleus)) {
                _processForReport(spectrum, nucleus, undefined, true, false, tasks[i].renderSpec || {}, statusPath);
                if (nucleus === "13C") {
                    _processForReport(spectrum, nucleus, 1, false, true, tasks[i].renderSpec || {}, statusPath);
                }
                _prepareSpectrumForExport(spectrum, nucleus, tasks[i].renderSpec || {}, tasks[i].graphicsProfilePath || "", statusPath);
                spectraByNucleus[nucleus] = spectrum;
            }
        }

        for (i = 0; i < spectraByTask.length && i < tasks.length; i++) {
            nucleus = tasks[i].nucleus;
            spectrum = spectraByTask[i];
            if (!spectrum || !spectrum.isValid() || !_isTwoDimensionalNucleus(nucleus)) {
                continue;
            }
            _prepareTwoDimensionalSpectrumForExport(spectrum, nucleus, tasks[i].renderSpec || {}, statusPath);
            verticalNucleus = _twoDimensionalVerticalNucleus(nucleus);
            _attachTraceSpectra(spectrum, spectraByNucleus["1H"], spectraByNucleus[verticalNucleus], statusPath);
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
            "contours.scaling",
            "contours.positivenumber",
            "contours.negativenumber",
            "contours.linewidth",
            "traces.horizontal.size",
            "traces.vertical.size",
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
