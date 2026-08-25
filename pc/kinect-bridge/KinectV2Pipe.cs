// KinectV2Pipe - pulls 1920x1080 frames from a Kinect for Xbox One (v2) via
// Kinect SDK 2.0 and writes raw YUY2 to stdout for ffmpeg to encode.
// Run via publish-kinect-v2.ps1.
//
// This is the v2 counterpart to KinectPipe.cs. Three things differ beyond the API:
//   - Resolution is 1920x1080 instead of 640x480 (9x the pixels).
//   - SDK 2.0 exposes NO writable exposure/gain/white-balance. ColorCameraSettings
//     is read-only, so the v2 is auto-exposure only. The v1's manual tuning has no
//     equivalent here - see docs/CAMERAS.md.
//   - We emit the sensor's NATIVE YUY2 (2 bytes/pixel) rather than converting to
//     BGRA (4 bytes/pixel). Converting cost more than the encode did: per-frame
//     managed conversion of 2M pixels starved ffmpeg to 2.4fps. Raw YUY2 halves
//     the bytes AND skips the conversion; ffmpeg reads it natively as yuyv422.
//
// Args (all optional):
//   --fps <15|30>   frames per second to emit, default 15. The sensor always runs
//                   at 30; 15 emits every other frame. Detection runs at 10fps
//                   downstream, so 15 loses nothing that matters.
//   --timeout <s>   seconds to wait for the sensor to become available, default 15.
using System;
using System.Collections.Concurrent;
using System.Globalization;
using System.Threading;
using Microsoft.Kinect;

class KinectV2Pipe
{
    static double Arg(string[] a, string name, double def)
    {
        for (int i = 0; i < a.Length - 1; i++)
            if (a[i] == name) return double.Parse(a[i + 1], CultureInfo.InvariantCulture);
        return def;
    }

    static void Main(string[] args)
    {
        int fps = (int)Arg(args, "--fps", 15);
        int emitEvery = (fps >= 30) ? 1 : 2;
        double timeout = Arg(args, "--timeout", 15);

        KinectSensor sensor = KinectSensor.GetDefault();
        if (sensor == null)
        {
            Console.Error.WriteLine("No Kinect v2 sensor. Check the Kinect Adapter for Windows is powered and on a USB 3.0 port.");
            Environment.Exit(1);
        }

        sensor.Open();

        // Open() is asynchronous - the sensor is not usable until IsAvailable flips.
        DateTime deadline = DateTime.UtcNow.AddSeconds(timeout);
        while (!sensor.IsAvailable && DateTime.UtcNow < deadline)
            System.Threading.Thread.Sleep(250);
        if (!sensor.IsAvailable)
        {
            Console.Error.WriteLine(
                "Kinect v2 did not become available within " + timeout + "s. " +
                "Check the adapter's power brick is plugged in, and that the sensor is on a USB 3.0 controller.");
            Environment.Exit(1);
        }

        FrameDescription desc = sensor.ColorFrameSource.CreateFrameDescription(ColorImageFormat.Yuy2);
        int width = desc.Width, height = desc.Height;
        int frameBytes = width * height * 2;      // YUY2 is 2 bytes per pixel

        Console.Error.WriteLine(string.Format(
            "Frame description: {0}x{1}, {2} bytes/px, buffer {3} bytes",
            width, height, desc.BytesPerPixel, frameBytes));

        // Capture and I/O are deliberately decoupled.
        //
        // Writing straight to stdout from inside FrameArrived looks simpler and is
        // what this bridge did first, but it blocks the sensor's callback whenever
        // the consumer applies backpressure. The Kinect service serialises on that
        // callback, so a momentary encoder stall collapses capture to ~2fps and
        // never recovers - even though the pipe alone sustains 30fps and the
        // encoder alone runs at 28x realtime. Measured, not theorised.
        //
        // So: the callback only copies into a free buffer and returns immediately;
        // a dedicated writer thread drains the queue. When the consumer falls
        // behind we drop the newest frame rather than stall the sensor, which is
        // the right trade for a live view.
        const int POOL = 4;
        var free = new ConcurrentQueue<byte[]>();
        for (int i = 0; i < POOL; i++) free.Enqueue(new byte[frameBytes]);
        var filled = new BlockingCollection<byte[]>(POOL);

        long seen = 0, emitted = 0, dropped = 0;
        bool reportedError = false;

        var writer = new Thread(delegate()
        {
            var stdout = Console.OpenStandardOutput();
            foreach (byte[] b in filled.GetConsumingEnumerable())
            {
                try { stdout.Write(b, 0, b.Length); stdout.Flush(); }
                catch (Exception ex)
                {
                    // Consumer went away (ffmpeg exited). Exit rather than linger
                    // as an orphan holding the sensor and our own binary open.
                    Console.Error.WriteLine("WRITE ERROR: " + ex.GetType().Name + ": " + ex.Message);
                    Environment.Exit(0);
                }
                free.Enqueue(b);
            }
        });
        writer.IsBackground = true;
        writer.Start();

        ColorFrameReader reader = sensor.ColorFrameSource.OpenReader();
        reader.FrameArrived += delegate(object o, ColorFrameArrivedEventArgs e)
        {
            try
            {
                using (ColorFrame f = e.FrameReference.AcquireFrame())
                {
                    if (f == null) return;               // frame already recycled; skip
                    if (seen++ % emitEvery != 0) return; // framerate divider

                    byte[] b;
                    if (!free.TryDequeue(out b))         // consumer behind: drop
                    {
                        if (++dropped % 100 == 0)
                            Console.Error.WriteLine("dropped frames (consumer behind): " + dropped);
                        return;
                    }
                    if (f.RawColorImageFormat == ColorImageFormat.Yuy2)
                        f.CopyRawFrameDataToArray(b);            // no conversion
                    else
                        f.CopyConvertedFrameDataToArray(b, ColorImageFormat.Yuy2);
                    filled.Add(b);
                    if (++emitted % 150 == 0)
                        Console.Error.WriteLine("frames emitted: " + emitted + ", dropped: " + dropped);
                }
            }
            catch (Exception ex)
            {
                // Without this the exception is swallowed by the event dispatch and
                // the symptom is simply "no frames", with no clue why.
                if (!reportedError)
                {
                    reportedError = true;
                    Console.Error.WriteLine("FRAME ERROR: " + ex.GetType().Name + ": " + ex.Message);
                }
            }
        };

        Console.Error.WriteLine(string.Format(
            "Kinect v2 streaming {0}x{1}@{2} YUY2 to stdout (sensor runs 30fps, emitting every {3}). Ctrl-C to stop.",
            width, height, fps, emitEvery));
        Console.Error.WriteLine("Note: SDK 2.0 has no manual exposure/white-balance control - auto only.");

        System.Threading.Thread.Sleep(System.Threading.Timeout.Infinite);
    }
}
