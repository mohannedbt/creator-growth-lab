namespace CreatorGrowthLab.UI.Models.Analytics
{
    public class AnalyticsRunSummary
    {
        public string RunId { get; set; } = default!;
        public string ChannelId { get; set; } = default!;
        public DateTime GeneratedAt { get; set; }

        public int VideosAnalyzed { get; set; }
        public int BaselineWindow { get; set; }

        public double BaselineViewsPerDay { get; set; }
        public double MedianRelativePerformance { get; set; }
    }
}
