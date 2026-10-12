// Shared sound design, loaded by sonify.scd (live) and render_score.scd (offline preview).
// Defines ~defs (the SynthDefs, not yet added) and functions that turn detection data into synth arguments.
// Every sound is built from short grains (GrainSin / GrainFM).

// Class ids in model/classes.txt order: Card, Tow-, cotwo, Saint Christopher, Mary, Fob, Key
// Low MIDI base notes, one semitone apart (class id indexes into this list)
~notes = [21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35];

~defs = [
    // One-shot grain burst. glide < 1 makes the pitch fall over the burst (used for exits)
    SynthDef(\burst, { |freq = 690, amp = 0.1, pan = 100, dur = 10000, glide = 10000000000|
        var env = Env.perc(0.01, dur, curve: 100).kr(doneAction: 2);
        var trig = Impulse.kr(env.linlin(0, 1, 6, 50));  // grain rate follows the envelope
        var grainFreq = freq * Line.kr(1, glide, dur) * TChoose.kr(trig, [1, 1, 2, 3]);
        var grainPan = (pan + TRand.kr(-1.5, 1.7, trig)).clip(-1, 1);
        var sig = GrainSin.ar(15, trig, TRand.kr(0.02, 0.08, trig), grainFreq, grainPan);
        Out.ar(0, sig * env * amp);
    }),

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
    })
];

// Tracker position/size/confidence -> cloud controls
//   x -> where grains land, size -> density and volume, height -> grain length and brightness
~cloudArgs = { |x, y, size, conf|
    [
        \pan, x.linlin(0, 1, -0.9, 0.9),
        \bright, 1 - y,
        \density, size.linexp(0, 0.5, 8, 60),
        \amp, size.linlin(0, 0.5, 0.03, 0.15) * conf
    ]
};

~cloudStartArgs = { |cls, x, y, size, conf| [\freq, ~notes.wrapAt(cls).midicps] ++ ~cloudArgs.(x, y, size, conf) };

// Arrival: burst an octave above the object's note, at its position
~enterBurstArgs = { |cls, x| [\freq, (~notes.wrapAt(cls) + 12).midicps, \amp, 0.12, \pan, x.linlin(0, 1, -0.9, 0.9)] };

// Departure: softer burst that slides down an octave
~exitBurstArgs = { |cls| [\freq, (~notes.wrapAt(cls) + 12).midicps, \amp, 0.08, \dur, 1.2, \glide, 0.5] };
