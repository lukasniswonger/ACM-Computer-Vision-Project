// Object Sonifier: turns detections from main.py into sound, live, using only granular synthesis.
//
// Start this before main.py:
//   SuperCollider IDE: open this file, click anywhere inside the outer parentheses, press Cmd+Return
//   Terminal:          /Applications/SuperCollider.app/Contents/MacOS/sclang supercollider/sonify.scd
//
// The sounds themselves are defined in sounds.scd. Every class has its own note.
//   appears:   a burst of sine grains at the object's note, dense at first and thinning out
//   on screen: a continuous cloud of FM grains that follows the object:
//              x position -> where grains land in the stereo field
//              size       -> grain density and volume (closer = thicker cloud)
//              height     -> grain length and brightness (higher on screen = shorter, brighter grains)
//   leaves:    a grain burst that slides down an octave, and the object's cloud fades out

(
"sounds.scd".loadRelative;
~voices = Dictionary.new;  // track id -> cloud Synth

// Output only. Leaving input on makes the server fail to boot when the mic and speakers
// run at different sample rates (common with Bluetooth headsets)
s.options.numInputBusChannels = 0;

s.waitForBoot {
    ~defs.do(_.add);
    s.sync;

    // /detect/enter track_id class_id class_name x y size confidence
    OSCdef(\detectEnter, { |msg|
        var id = msg[1], cls = msg[2], name = msg[3], x = msg[4], y = msg[5], size = msg[6], conf = msg[7];
        "+ % #%".format(name, id).postln;
        Synth(\burst, ~enterBurstArgs.(cls, x));
        ~voices[id] !? { |v| v.set(\gate, 0) };
        ~voices[id] = Synth(\cloud, ~cloudStartArgs.(cls, x, y, size, conf));
    }, '/detect/enter');

    // /detect/update track_id x y size confidence
    OSCdef(\detectUpdate, { |msg|
        ~voices[msg[1]] !? { |v| v.set(*~cloudArgs.(msg[2], msg[3], msg[4], msg[5])) };
    }, '/detect/update');

    // /detect/exit track_id class_id class_name seconds_on_screen
    OSCdef(\detectExit, { |msg|
        var id = msg[1], cls = msg[2], name = msg[3], seconds = msg[4];
        "- % #% (%s on screen)".format(name, id, seconds.round(0.1)).postln;
        Synth(\burst, ~exitBurstArgs.(cls));
        ~voices.removeAt(id) !? { |v| v.set(\gate, 0) };
    }, '/detect/exit');

    // /detect/clear (sent when main.py finishes)
    OSCdef(\detectClear, {
        ~voices.do { |v| v.set(\gate, 0) };
        ~voices.clear;
        "cleared".postln;
    }, '/detect/clear');

    "Object Sonifier ready, listening on port %".format(NetAddr.langPort).postln;
};
)
