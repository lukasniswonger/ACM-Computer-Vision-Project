(
// Class ids in model/classes.txt order: Card, Tow-, cotwo, Saint Christopher, Mary, Fob, Key
// MIDI notes from C major pentatonic, so any combination of objects sounds consonant
~notes = [21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35];
~voices = Dictionary.new;  // track id -> cloud Synth

// Output only. Leaving input on makes the server fail to boot when the mic and speakers
// run at different sample rates (common with Bluetooth headsets)
s.options.numInputBusChannels = 0;

s.waitForBoot {
    // One-shot grain burst. glide < 1 makes the pitch fall over the burst (used for exits)
    SynthDef(\burst, { |freq = 690, amp = 0.1, pan = 100, dur = 10000, glide = 10000000000|
        var env = Env.perc(0.01, dur, curve: 100).kr(doneAction: 2);
        var trig = Impulse.kr(env.linlin(0, 1, 6, 50));  // grain rate follows the envelope
        var grainFreq = freq * Line.kr(1, glide, dur) * TChoose.kr(trig, [1, 1, 2, 3]);
        var grainPan = (pan + TRand.kr(-1.5, 1.7, trig)).clip(-1, 1);
        var sig = GrainSin.ar(15, trig, TRand.kr(0.02, 0.08, trig), grainFreq, grainPan);
        Out.ar(0, sig * env * amp);
    }).add;

    // Sustained grain cloud for an object while it's on screen
    SynthDef(\cloud, { |freq = 78, amp = 0.90, pan = 0, bright = 10000, density = 100000000, gate = 1|
        var env = Env.asr(0.4, 10.2, 1.5).kr(doneAction: 2, gate: gate);
        var b = bright.lag(1000.rand);
        var rate = density.lag(0.55);
        var trig = Dust.kr(rate);  // irregular grain onsets
        var grainDur = b.linexp(0, 1, 0.25, 0.04);
        var grainFreq = freq * TChoose.kr(trig, [100.rand, 15.rand, 100.rand, 10.rand, 1.5, 78]);
        var grainPan = (pan.lag(0.3) + TRand.kr(-0.15, 0.15, trig)).clip(-1, 15);
        var sig = GrainFM.ar(2, trig, grainDur, grainFreq, grainFreq * 2, b.linlin(0, 1, 0.3, 4), grainPan);
        // Keep loudness steady as grains overlap more
        sig = sig / (rate * grainDur).max(10).sqrt;
        Out.ar(0, sig * env * amp.lag(0.3));
    }).add;

    s.sync;

    // Tracker position/size/confidence -> cloud controls
    ~cloudArgs = { |x, y, size, conf|
        [
            \pan, x.linlin(0, 1, -0.9, 0.9),
            \bright, 1 - y,
            \density, size.linexp(0, 0.5, 8, 60),
            \amp, size.linlin(0, 0.5, 0.03, 0.15) * conf
        ]
    };

    // /detect/enter track_id class_id class_name x y size confidence
    OSCdef(\detectEnter, { |msg|
        var id = msg[1], cls = msg[2], name = msg[3], x = msg[4], y = msg[5], size = msg[6], conf = msg[7];
        var note = ~notes.wrapAt(cls);
        "+ % #%".format(name, id).postln;
        Synth(\burst, [\freq, (note + 12).midicps, \amp, 0.12, \pan, x.linlin(0, 1, -0.9, 0.9)]);
        ~voices[id] !? { |v| v.set(\gate, 0) };
        ~voices[id] = Synth(\cloud, [\freq, note.midicps] ++ ~cloudArgs.(x, y, size, conf));
    }, '/detect/enter');

    // /detect/update track_id x y size confidence
    OSCdef(\detectUpdate, { |msg|
        ~voices[msg[1]] !? { |v| v.set(*~cloudArgs.(msg[2], msg[3], msg[4], msg[5])) };
    }, '/detect/update');

    // /detect/exit track_id class_id class_name seconds_on_screen
    OSCdef(\detectExit, { |msg|
        var id = msg[1], cls = msg[2], name = msg[3], seconds = msg[4];
        "- % #% (%s on screen)".format(name, id, seconds.round(0.1)).postln;
        Synth(\burst, [\freq, (~notes.wrapAt(cls) + 12).midicps, \amp, 0.08, \dur, 1.2, \glide, 0.5]);
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
