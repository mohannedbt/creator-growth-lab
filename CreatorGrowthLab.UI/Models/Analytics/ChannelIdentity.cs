using System.Text.Json.Serialization;
namespace CreatorGrowthLab.UI.Models.Analytics
{
    public class ChannelIdentity
    {
        [JsonPropertyName("channel_id")]
        public string ChannelId { get; set; } = "";

        [JsonPropertyName("title")]
        public string Title { get; set; } = "";

        [JsonPropertyName("thumbnail_url")]
        public string ThumbnailUrl { get; set; } = "";
    }

}
