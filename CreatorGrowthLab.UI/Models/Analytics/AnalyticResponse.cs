using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace CreatorGrowthLab.UI.Models.Analytics
{
    public class AnalyticsResponse
    {
        [JsonPropertyName("meta")]
        public MetaInfo Meta { get; set; } = new();

        [JsonPropertyName("kpis")]
        public Kpis Kpis { get; set; } = new();

        [JsonPropertyName("trends")]
        public List<TrendPoint> Trends { get; set; } = new();

        [JsonPropertyName("drivers")]
        public List<DriverEffect> Drivers { get; set; } = new();

        [JsonPropertyName("recommendations")]
        public List<Recommendation> Recommendations { get; set; } = new();

        [JsonPropertyName("warnings")]
        public List<string> Warnings { get; set; } = new();
        [JsonPropertyName("channel")]
        public ChannelIdentity Channel { get; set; }   // ✅

    }

    public class MetaInfo
    {
        [JsonPropertyName("channel_id")]
        public string ChannelId { get; set; } = "";

        [JsonPropertyName("n_videos")]
        public int NVideos { get; set; }

        [JsonPropertyName("baseline_window")]
        public int BaselineWindow { get; set; }

        [JsonPropertyName("generated_at")]
        public DateTime GeneratedAt { get; set; }
    }

    public class Kpis
    {
        [JsonPropertyName("videos_analyzed")]
        public int VideosAnalyzed { get; set; }

        [JsonPropertyName("baseline_views_per_day")]
        public double BaselineViewsPerDay { get; set; }

        [JsonPropertyName("median_relative_performance")]
        public double MedianRelativePerformance { get; set; }

        [JsonPropertyName("avg_engagement_rate")]
        public double AvgEngagementRate { get; set; }
    }

    public class TrendPoint
    {
        [JsonPropertyName("published_at")]
        public DateTime PublishedAt { get; set; }

        [JsonPropertyName("views")]
        public long Views { get; set; }

        [JsonPropertyName("views_per_day")]
        public double ViewsPerDay { get; set; }

        [JsonPropertyName("relative_performance")]
        public double RelativePerformance { get; set; }
    }

    public class DriverEffect
    {
        [JsonPropertyName("feature")]
        public string Feature { get; set; } = "";

        [JsonPropertyName("effect_percent")]
        public double EffectPercent { get; set; }

        [JsonPropertyName("unit_change")]
        public string UnitChange { get; set; } = "";

        [JsonPropertyName("direction")]
        public string Direction { get; set; } = "";
    }

    public class Recommendation
    {
        [JsonPropertyName("title")]
        public string Title { get; set; } = "";

        [JsonPropertyName("detail")]
        public string Detail { get; set; } = "";

        [JsonPropertyName("expected_impact_percent")]
        public double ExpectedImpactPercent { get; set; }

        [JsonPropertyName("confidence")]
        public string Confidence { get; set; } = "";
    }
}
