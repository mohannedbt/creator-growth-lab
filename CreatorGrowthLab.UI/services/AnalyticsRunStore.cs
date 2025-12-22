using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using CreatorGrowthLab.UI.Models.Analytics;
using Microsoft.Extensions.Configuration;

namespace CreatorGrowthLab.UI.Services
{
    public class AnalyticsRunStore
    {
        private readonly string _resultsDir;

        public AnalyticsRunStore(IConfiguration config)
        {
            _resultsDir = config["AnalyticsStorage:ResultsDir"]
                          ?? "App_Data/results";
        }

        public string ResultsDir => _resultsDir;

        public async Task<List<RunListItem>> ListRunsAsync(CancellationToken ct = default)
        {
            Directory.CreateDirectory(_resultsDir);

            var files = Directory.EnumerateFiles(_resultsDir, "*.json", SearchOption.TopDirectoryOnly)
                                 .OrderByDescending(f => File.GetLastWriteTimeUtc(f))
                                 .ToList();

            var list = new List<RunListItem>();

            foreach (var path in files)
            {
                ct.ThrowIfCancellationRequested();
                try
                {
                    var text = await File.ReadAllTextAsync(path, ct);
                    var resp = JsonSerializer.Deserialize<AnalyticsResponse>(text, JsonOptions());

                    if (resp?.Meta == null || resp.Kpis == null) continue;

                    list.Add(new RunListItem
                    {
                        FileName = Path.GetFileName(path),
                        ChannelId = resp.Meta.ChannelId,
                        GeneratedAtUtc = resp.Meta.GeneratedAt.ToUniversalTime(),
                        NVideos = resp.Meta.NVideos,
                        BaselineWindow = resp.Meta.BaselineWindow,
                        BaselineViewsPerDay = resp.Kpis.BaselineViewsPerDay,
                        MedianRelativePerformance = resp.Kpis.MedianRelativePerformance,
                        AvgEngagementRate = resp.Kpis.AvgEngagementRate
                    });
                }
                catch
                {
                    // skip corrupted/partial files
                }
            }

            return list.OrderByDescending(x => x.GeneratedAtUtc).ToList();
        }

        public async Task<AnalyticsResponse?> ReadRunAsync(string fileName, CancellationToken ct = default)
        {
            Directory.CreateDirectory(_resultsDir);

            // protect against ../ traversal
            var safe = Path.GetFileName(fileName);
            var path = Path.Combine(_resultsDir, safe);

            if (!System.IO.File.Exists(path))
                return null;

            var text = await File.ReadAllTextAsync(path, ct);
            return JsonSerializer.Deserialize<AnalyticsResponse>(text, JsonOptions());
        }

        private static JsonSerializerOptions JsonOptions() =>
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            };
    }

    public class RunListItem
    {
        public string FileName { get; set; } = "";
        public string ChannelId { get; set; } = "";
        public DateTime GeneratedAtUtc { get; set; }
        public int NVideos { get; set; }
        public int BaselineWindow { get; set; }
        public double BaselineViewsPerDay { get; set; }
        public double MedianRelativePerformance { get; set; }
        public double AvgEngagementRate { get; set; }
    }
}
