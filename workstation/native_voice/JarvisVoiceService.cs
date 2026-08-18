using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Speech.Recognition;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace JarvisNativeVoice
{
    public static class JarvisVoiceService
    {
        private sealed class VoiceEvent
        {
            public long Id;
            public string Type;
            public string Text;
            public float Confidence;
            public DateTime TimestampUtc;
        }

        private static readonly object Sync =
            new object();

        private static readonly List<VoiceEvent> Events =
            new List<VoiceEvent>();

        private static readonly string[] WakePhrases =
        {
            "jarvis",
            "hey jarvis",
            "hello jarvis",
            "hi jarvis"
        };

        private static readonly string[] StopPhrases =
        {
            "stop",
            "jarvis stop",
            "stop talking",
            "be quiet",
            "quiet"
        };

        private static long nextEventId =
            0;

        private static bool speaking =
            false;

        private static volatile bool running =
            true;

        private static SpeechRecognitionEngine recognizer;

        private static TcpListener listener;

        private const int Port =
            8798;

        private const float WakeThreshold =
            0.58f;

        private const float StopThreshold =
            0.52f;

        private static string Normalize(
            string value
        )
        {
            return (
                value
                ?? ""
            )
            .Trim()
            .ToLowerInvariant();
        }

        private static bool Matches(
            string value,
            string[] choices
        )
        {
            string normalized =
                Normalize(
                    value
                );

            foreach (
                string item
                in choices
            )
            {
                if (
                    String.Equals(
                        normalized,
                        item,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    return true;
                }
            }

            return false;
        }

        private static void AddEvent(
            string type,
            string text,
            float confidence
        )
        {
            lock (Sync)
            {
                nextEventId++;

                Events.Add(
                    new VoiceEvent
                    {
                        Id =
                            nextEventId,

                        Type =
                            type,

                        Text =
                            text,

                        Confidence =
                            confidence,

                        TimestampUtc =
                            DateTime.UtcNow
                    }
                );

                if (
                    Events.Count
                    > 100
                )
                {
                    Events.RemoveRange(
                        0,
                        Events.Count - 100
                    );
                }
            }

            Console.WriteLine(
                "EVENT "
                + type.ToUpperInvariant()
                + " | "
                + text
                + " | "
                + confidence.ToString(
                    "0.00",
                    CultureInfo.InvariantCulture
                )
            );
        }

        private static RecognizerInfo SelectRecognizer()
        {
            var installed =
                SpeechRecognitionEngine
                .InstalledRecognizers();

            if (
                installed == null
                ||
                installed.Count == 0
            )
            {
                return null;
            }

            foreach (
                RecognizerInfo info
                in installed
            )
            {
                if (
                    info.Culture.Name.Equals(
                        "en-US",
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    return info;
                }
            }

            return installed[0];
        }

        private static void StartRecognizer()
        {
            RecognizerInfo selected =
                SelectRecognizer();

            if (
                selected == null
            )
            {
                throw new InvalidOperationException(
                    "No Windows speech recognizer is installed."
                );
            }

            recognizer =
                new SpeechRecognitionEngine(
                    selected
                );

            Choices controls =
                new Choices();

            controls.Add(
                WakePhrases
            );

            controls.Add(
                StopPhrases
            );

            GrammarBuilder builder =
                new GrammarBuilder(
                    controls
                );

            builder.Culture =
                selected.Culture;

            Grammar grammar =
                new Grammar(
                    builder
                );

            grammar.Name =
                "jarvis-control";

            recognizer.LoadGrammar(
                grammar
            );

            recognizer.SpeechRecognized +=
                delegate(
                    object sender,
                    SpeechRecognizedEventArgs args
                )
                {
                    string text =
                        Normalize(
                            args.Result.Text
                        );

                    float confidence =
                        args.Result.Confidence;

                    bool isSpeaking;

                    lock (Sync)
                    {
                        isSpeaking =
                            speaking;
                    }

                    if (
                        Matches(
                            text,
                            StopPhrases
                        )
                        &&
                        confidence
                        >= StopThreshold
                    )
                    {
                        AddEvent(
                            "stop",
                            text,
                            confidence
                        );

                        return;
                    }

                    // While JARVIS is speaking, native recognition
                    // is intentionally control-only. Wake events are
                    // suppressed so JARVIS saying its own name cannot
                    // start another command.
                    if (isSpeaking)
                    {
                        return;
                    }

                    if (
                        Matches(
                            text,
                            WakePhrases
                        )
                        &&
                        confidence
                        >= WakeThreshold
                    )
                    {
                        AddEvent(
                            "wake",
                            text,
                            confidence
                        );
                    }
                };

            recognizer.SetInputToDefaultAudioDevice();

            recognizer.RecognizeAsync(
                RecognizeMode.Multiple
            );

            Console.WriteLine(
                "NATIVE CONTROL: READY | "
                + selected.Culture.Name
            );
        }

        private static string JsonEscape(
            string value
        )
        {
            if (
                value == null
            )
            {
                return "";
            }

            return (
                value
                .Replace(
                    "\\",
                    "\\\\"
                )
                .Replace(
                    "\"",
                    "\\\""
                )
                .Replace(
                    "\r",
                    "\\r"
                )
                .Replace(
                    "\n",
                    "\\n"
                )
            );
        }

        private static string HealthJson()
        {
            bool currentSpeaking;

            lock (Sync)
            {
                currentSpeaking =
                    speaking;
            }

            return (
                "{"
                + "\"success\":true,"
                + "\"service\":\"jarvis-native-voice\","
                + "\"version\":\"3.2\","
                + "\"speaking\":"
                + (
                    currentSpeaking
                    ? "true"
                    : "false"
                )
                + "}"
            );
        }

        private static string EventsJson(
            long after
        )
        {
            StringBuilder builder =
                new StringBuilder();

            builder.Append(
                "{\"success\":true,\"events\":["
            );

            bool first =
                true;

            lock (Sync)
            {
                foreach (
                    VoiceEvent item
                    in Events
                )
                {
                    if (
                        item.Id
                        <= after
                    )
                    {
                        continue;
                    }

                    if (!first)
                    {
                        builder.Append(
                            ","
                        );
                    }

                    first =
                        false;

                    builder.Append(
                        "{"
                    );

                    builder.Append(
                        "\"id\":"
                        + item.Id
                    );

                    builder.Append(
                        ",\"type\":\""
                        + JsonEscape(
                            item.Type
                        )
                        + "\""
                    );

                    builder.Append(
                        ",\"text\":\""
                        + JsonEscape(
                            item.Text
                        )
                        + "\""
                    );

                    builder.Append(
                        ",\"confidence\":"
                        + item.Confidence.ToString(
                            "0.000",
                            CultureInfo.InvariantCulture
                        )
                    );

                    builder.Append(
                        ",\"timestamp\":\""
                        + item.TimestampUtc.ToString(
                            "o",
                            CultureInfo.InvariantCulture
                        )
                        + "\""
                    );

                    builder.Append(
                        "}"
                    );
                }
            }

            builder.Append(
                "]}"
            );

            return builder.ToString();
        }

        private static long QueryAfter(
            string target
        )
        {
            Match match =
                Regex.Match(
                    target
                    ?? "",
                    @"(?:\?|&)after=(\d+)",
                    RegexOptions.IgnoreCase
                );

            long value;

            if (
                match.Success
                &&
                Int64.TryParse(
                    match.Groups[1].Value,
                    out value
                )
            )
            {
                return value;
            }

            return 0;
        }

        private static void ApplyState(
            string body
        )
        {
            bool newSpeaking =
                Regex.IsMatch(
                    body
                    ?? "",
                    "\"speaking\"\\s*:\\s*true",
                    RegexOptions.IgnoreCase
                );

            lock (Sync)
            {
                speaking =
                    newSpeaking;
            }
        }

        private static void WriteResponse(
            NetworkStream stream,
            int status,
            string body
        )
        {
            byte[] payload =
                Encoding.UTF8.GetBytes(
                    body
                    ?? "{}"
                );

            string statusText =
                (
                    status == 200
                    ? "OK"
                    : (
                        status == 204
                        ? "No Content"
                        : "Error"
                    )
                );

            string headers =
                "HTTP/1.1 "
                + status
                + " "
                + statusText
                + "\r\n"
                + "Content-Type: application/json; charset=utf-8\r\n"
                + "Content-Length: "
                + payload.Length
                + "\r\n"
                + "Cache-Control: no-store\r\n"
                + "Access-Control-Allow-Origin: http://127.0.0.1:8797\r\n"
                + "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
                + "Access-Control-Allow-Headers: Content-Type\r\n"
                + "Connection: close\r\n"
                + "\r\n";

            byte[] headerBytes =
                Encoding.ASCII.GetBytes(
                    headers
                );

            stream.Write(
                headerBytes,
                0,
                headerBytes.Length
            );

            if (
                payload.Length > 0
            )
            {
                stream.Write(
                    payload,
                    0,
                    payload.Length
                );
            }
        }

        private static void HandleClient(
            TcpClient client
        )
        {
            using (client)
            using (
                NetworkStream stream =
                    client.GetStream()
            )
            {
                stream.ReadTimeout =
                    2500;

                StreamReader reader =
                    new StreamReader(
                        stream,
                        Encoding.UTF8,
                        false,
                        4096,
                        true
                    );

                string requestLine =
                    reader.ReadLine();

                if (
                    String.IsNullOrWhiteSpace(
                        requestLine
                    )
                )
                {
                    return;
                }

                string[] parts =
                    requestLine.Split(
                        ' '
                    );

                if (
                    parts.Length < 2
                )
                {
                    WriteResponse(
                        stream,
                        400,
                        "{\"success\":false}"
                    );

                    return;
                }

                string method =
                    parts[0]
                    .Trim()
                    .ToUpperInvariant();

                string target =
                    parts[1]
                    .Trim();

                int contentLength =
                    0;

                while (true)
                {
                    string header =
                        reader.ReadLine();

                    if (
                        header == null
                        ||
                        header.Length == 0
                    )
                    {
                        break;
                    }

                    int colon =
                        header.IndexOf(
                            ':'
                        );

                    if (
                        colon <= 0
                    )
                    {
                        continue;
                    }

                    string name =
                        header.Substring(
                            0,
                            colon
                        )
                        .Trim();

                    string value =
                        header.Substring(
                            colon + 1
                        )
                        .Trim();

                    if (
                        name.Equals(
                            "Content-Length",
                            StringComparison.OrdinalIgnoreCase
                        )
                    )
                    {
                        Int32.TryParse(
                            value,
                            out contentLength
                        );
                    }
                }

                string body =
                    "";

                if (
                    contentLength > 0
                    &&
                    contentLength <= 4096
                )
                {
                    char[] chars =
                        new char[
                            contentLength
                        ];

                    int total =
                        0;

                    while (
                        total
                        < chars.Length
                    )
                    {
                        int read =
                            reader.Read(
                                chars,
                                total,
                                chars.Length - total
                            );

                        if (
                            read <= 0
                        )
                        {
                            break;
                        }

                        total +=
                            read;
                    }

                    body =
                        new string(
                            chars,
                            0,
                            total
                        );
                }

                if (
                    method == "OPTIONS"
                )
                {
                    WriteResponse(
                        stream,
                        204,
                        ""
                    );

                    return;
                }

                if (
                    method == "GET"
                    &&
                    target.StartsWith(
                        "/health",
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    WriteResponse(
                        stream,
                        200,
                        HealthJson()
                    );

                    return;
                }

                if (
                    method == "GET"
                    &&
                    target.StartsWith(
                        "/events",
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    WriteResponse(
                        stream,
                        200,
                        EventsJson(
                            QueryAfter(
                                target
                            )
                        )
                    );

                    return;
                }

                if (
                    method == "POST"
                    &&
                    target.StartsWith(
                        "/state",
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                {
                    ApplyState(
                        body
                    );

                    WriteResponse(
                        stream,
                        200,
                        HealthJson()
                    );

                    return;
                }

                WriteResponse(
                    stream,
                    404,
                    "{\"success\":false,\"error\":\"not found\"}"
                );
            }
        }

        private static void ServeHttp()
        {
            listener =
                new TcpListener(
                    IPAddress.Loopback,
                    Port
                );

            listener.Start();

            Console.WriteLine(
                "CONTROL API: http://127.0.0.1:"
                + Port
            );

            while (running)
            {
                try
                {
                    TcpClient client =
                        listener.AcceptTcpClient();

                    ThreadPool.QueueUserWorkItem(
                        delegate
                        {
                            try
                            {
                                HandleClient(
                                    client
                                );
                            }
                            catch
                            {
                                try
                                {
                                    client.Close();
                                }
                                catch
                                {
                                }
                            }
                        }
                    );
                }
                catch
                {
                    if (!running)
                    {
                        return;
                    }
                }
            }
        }

        public static int Main()
        {
            Console.WriteLine(
                "============================================================"
            );

            Console.WriteLine(
                "JARVIS NATIVE VOICE CONTROL V3.2"
            );

            Console.WriteLine(
                "============================================================"
            );

            try
            {
                StartRecognizer();
            }
            catch (
                Exception exc
            )
            {
                Console.WriteLine(
                    "VOICE START ERROR: "
                    + exc.Message
                );

                return 3;
            }

            try
            {
                ServeHttp();
            }
            catch (
                Exception exc
            )
            {
                Console.WriteLine(
                    "HTTP START ERROR: "
                    + exc.Message
                );

                return 4;
            }
            finally
            {
                running =
                    false;

                try
                {
                    listener.Stop();
                }
                catch
                {
                }

                try
                {
                    recognizer.RecognizeAsyncCancel();
                }
                catch
                {
                }

                try
                {
                    recognizer.Dispose();
                }
                catch
                {
                }
            }

            return 0;
        }
    }
}
