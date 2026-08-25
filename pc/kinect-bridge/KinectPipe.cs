// KinectPipe - pulls RGB frames from a Kinect v1 (model 1517) via SDK 1.8 and
// writes raw BGRA to stdout for ffmpeg to encode. Run via publish-kinect.ps1,
// which pipes it into ffmpeg through cmd.exe (a PowerShell pipe would corrupt
// the binary stream).
//
// Camera control args (all optional):
//   --auto                 use auto exposure (default is manual)
//   --brightness <0..1>    auto-exposure target, default 0.13 (with --auto)
//   --exposure <1..4000>   manual exposure in 1/10000 s units, default 20
//   --gain <1..16>         manual gain, default 1.0
//   --wb <2700..6500>      fixed white balance in Kelvin, default 4700
//                          (auto white balance is always off - it causes the
//                           pink flicker under office lighting)
using System;
using System.Globalization;
using Microsoft.Kinect;

class KinectPipe
{
    static double Arg(string[] a, string name, double def)
    {
        for (int i = 0; i < a.Length - 1; i++)
            if (a[i] == name) return double.Parse(a[i + 1], CultureInfo.InvariantCulture);
        return def;
    }
    static bool Has(string[] a, string name)
    {
        foreach (string s in a) if (s == name) return true;
        return false;
    }

    static void Main(string[] args)
    {
        KinectSensor sensor = null;
        foreach (KinectSensor s in KinectSensor.KinectSensors)
        {
            Console.Error.WriteLine("Sensor found: status " + s.Status);
            if (s.Status == KinectStatus.Connected) { sensor = s; break; }
        }
        if (sensor == null)
        {
            Console.Error.WriteLine(
                "No usable Kinect. If a sensor was listed as NotPowered, plug in its AC adapter; " +
                "if none was listed at all, Windows doesn't see it on USB.");
            Environment.Exit(1);
        }

        sensor.ColorStream.Enable(ColorImageFormat.RgbResolution640x480Fps30);
        var stdout = Console.OpenStandardOutput();
        var buf = new byte[sensor.ColorStream.FramePixelDataLength];

        sensor.ColorFrameReady += delegate(object o, ColorImageFrameReadyEventArgs e)
        {
            using (ColorImageFrame f = e.OpenColorImageFrame())
            {
                if (f == null) return;
                f.CopyPixelDataTo(buf);
                stdout.Write(buf, 0, buf.Length);
            }
        };

        sensor.Start();

        ColorCameraSettings cs = sensor.ColorStream.CameraSettings;
        cs.AutoWhiteBalance = false;
        cs.WhiteBalance = (int)Arg(args, "--wb", 4700);
        if (Has(args, "--auto"))
        {
            cs.AutoExposure = true;
            cs.Brightness = Arg(args, "--brightness", 0.13);
        }
        else
        {
            cs.AutoExposure = false;
            cs.ExposureTime = Arg(args, "--exposure", 20);
            cs.Gain = Arg(args, "--gain", 1.0);
        }
        Console.Error.WriteLine(string.Format(
            "Camera: AutoExposure={0} ExposureTime={1} Gain={2} Brightness={3} AWB={4} WhiteBalance={5}K",
            cs.AutoExposure, cs.ExposureTime, cs.Gain, cs.Brightness, cs.AutoWhiteBalance, cs.WhiteBalance));

        Console.Error.WriteLine("Kinect streaming 640x480@30 BGRA to stdout. Ctrl-C to stop.");
        System.Threading.Thread.Sleep(System.Threading.Timeout.Infinite);
    }
}
