// Renders the detection messages recorded by `main.py --render-preview` to a WAV file, offline.
// Uses the same sounds as the live sonify.scd, but every sound lands exactly on its video timestamp,
// however fast or slow detection ran.
//
//   sclang supercollider/render_score.scd <score.scd> <out.wav> <duration_seconds>
//
// main.py runs this for you; the score file is an array of [video_time, address, args...] entries.

(
var argv = thisProcess.argv;
var events, bundles, nodes = Dictionary.new, nextNode = 1000, duration;

"sounds.scd".loadRelative;
events = File.readAllString(argv[0]).interpret;
duration = argv[2].asFloat;

// Load the SynthDefs at time 0, then translate each live OSC message into the server command it caused
bundles = ~defs.collect { |def| [0.0, [\d_recv, def.asBytes]] };
events.do { |e|
    var t = e[0], address = e[1], m = e[2..];
    switch(address,
        "/detect/enter", {
            // m: track_id class_id class_name x y size confidence
            var node = nextNode;
            nextNode = nextNode + 1;
            nodes[m[0]] !? { |old| bundles = bundles.add([t, [\n_set, old, \gate, 0]]) };
            nodes[m[0]] = node;
            bundles = bundles.add([t, [\s_new, \burst, -1, 0, 0] ++ ~enterBurstArgs.(m[1], m[3])]);
            bundles = bundles.add([t, [\s_new, \cloud, node, 0, 0] ++ ~cloudStartArgs.(m[1], m[3], m[4], m[5], m[6])]);
        },
        "/detect/update", {
            // m: track_id x y size confidence
            nodes[m[0]] !? { |node| bundles = bundles.add([t, [\n_set, node] ++ ~cloudArgs.(m[1], m[2], m[3], m[4])]) };
        },
        "/detect/exit", {
            // m: track_id class_id class_name seconds_on_screen
            bundles = bundles.add([t, [\s_new, \burst, -1, 0, 0] ++ ~exitBurstArgs.(m[1])]);
            nodes.removeAt(m[0]) !? { |node| bundles = bundles.add([t, [\n_set, node, \gate, 0]]) };
        },
        "/detect/clear", {
            nodes.do { |node| bundles = bundles.add([t, [\n_set, node, \gate, 0]]) };
            nodes.clear;
        }
    );
};

"Rendering % events, %s of audio to %".format(events.size, duration.round(0.1), argv[1]).postln;
Score(bundles).recordNRT(
    outputFilePath: argv[1],
    headerFormat: "WAV",
    sampleFormat: "int24",
    sampleRate: 48000,
    options: ServerOptions.new.numOutputBusChannels_(2).numInputBusChannels_(0),
    duration: duration,
    action: { "Rendered %".format(argv[1]).postln; 0.exit }
);
)
