// Object Sonifier: turns detections from main.py into sound.
//
// Start this before main.py:
//   SuperCollider IDE: open this file, click anywhere inside the outer parentheses, press Cmd+Return
//   Terminal:          /Applications/SuperCollider.app/Contents/MacOS/sclang supercollider/sonify.scd
//
// Every class has its own note. When an object appears, a bell plays and a drone starts for it.
// While it stays on screen, the drone follows it:
//   x position -> stereo pan, size -> volume, height on screen -> brightness (higher = brighter)
// When it leaves, a lower bell plays and its drone fades out.

(
// Class ids in model/classes.txt order: Card, Tow-, cotwo, Saint Christopher, Mary, Fob, Key
// MIDI notes from C major pentatonic, so any combination of objects sounds consonant
~notes = [60, 76, 79, 64, 67, 55, 62];
~voices = Dictionary.new;  // track id -> drone Synth

// Output only. Leaving input on makes the server fail to boot when the mic and speakers
// run at different sample rates (common with Bluetooth headsets)
s.options.numInputBusChannels = 0;

s.waitForBoot {
    SynthDef(\bell, { |freq = 440, amp = 0.2, pan = 0|
        var env = Env.perc(0.005, 1.8, curve: -6).kr(doneAction: 2);
        var sig = SinOsc.ar(freq * [1, 2.76, 5.4], 0, [1, 0.35, 0.12]).sum;
        Out.ar(0, Pan2.ar(sig * env * amp, pan));
    }).add;

    SynthDef(\drone, { |freq = 220, amp = 0.05, pan = 0, bright = 0.5, gate = 1|
        var env = Env.asr(0.4, 1, 1.5).kr(doneAction: 2, gate: gate);
        var sig = Saw.ar(freq * [1, 1.004, 0.996]).sum / 3;
        sig = RLPF.ar(sig, bright.lag(0.3).linexp(0, 1, 250, 3500), 0.4);
        Out.ar(0, Pan2.ar(sig * env * amp.lag(0.3), pan.lag(0.3)));
    }).add;

    s.sync;

    // Tracker position/size/confidence -> drone controls
    ~droneArgs = { |x, y, size, conf|
        [
            \pan, x.linlin(0, 1, -0.9, 0.9),
            \bright, 1 - y,
            \amp, size.linlin(0, 0.5, 0.02, 0.12) * conf
        ]
    };

    // /detect/enter track_id class_id class_name x y size confidence
    OSCdef(\detectEnter, { |msg|
        var id = msg[1], cls = msg[2], name = msg[3], x = msg[4], y = msg[5], size = msg[6], conf = msg[7];
        var note = ~notes.wrapAt(cls);
        "+ % #%".format(name, id).postln;
        Synth(\bell, [\freq, (note + 12).midicps, \amp, 0.2, \pan, x.linlin(0, 1, -0.9, 0.9)]);
        ~voices[id] !? { |v| v.set(\gate, 0) };
        ~voices[id] = Synth(\drone, [\freq, (note - 12).midicps] ++ ~droneArgs.(x, y, size, conf));
    }, '/detect/enter');

    // /detect/update track_id x y size confidence
    OSCdef(\detectUpdate, { |msg|
        ~voices[msg[1]] !? { |v| v.set(*~droneArgs.(msg[2], msg[3], msg[4], msg[5])) };
    }, '/detect/update');

    // /detect/exit track_id class_id class_name seconds_on_screen
    OSCdef(\detectExit, { |msg|
        var id = msg[1], cls = msg[2], name = msg[3], seconds = msg[4];
        "- % #% (%s on screen)".format(name, id, seconds.round(0.1)).postln;
        Synth(\bell, [\freq, ~notes.wrapAt(cls).midicps, \amp, 0.12]);
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
