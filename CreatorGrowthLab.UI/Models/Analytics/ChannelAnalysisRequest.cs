using System.Text.Json.Serialization;

namespace CreatorGrowthLab.UI.Models.Analytics
{
    public class ChannelAnalysisRequest
    {
        [JsonPropertyName("channel_id")]
        public string ChannelId { get; set; } = "";

        [JsonPropertyName("n_videos")]
        public int NVideos { get; set; } = 30;

        [JsonPropertyName("baseline_window")]
        public int BaselineWindow { get; set; } = 20;
    }
}
