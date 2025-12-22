using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using CreatorGrowthLab.UI.Models.Analytics;

namespace CreatorGrowthLab.UI.Services
{
    public class YouTubeChannelService
    {
        private readonly HttpClient _http;

        public YouTubeChannelService(HttpClient http)
        {
            _http = http;
            _http.DefaultRequestHeaders.UserAgent.ParseAdd(
                "CreatorGrowthLab/1.0 (contact: dev@local)");
        }

        public async Task<ChannelIdentity> GetChannelIdentityAsync(string channelId)
        {
            // 1️⃣ Try oEmbed with channel URL
            var identity = await TryOEmbedAsync(
                $"https://www.youtube.com/channel/{channelId}",
                channelId);

            if (identity != null)
                return identity;

            // 2️⃣ Hard fallback: deterministic avatar
            return new ChannelIdentity
            {
                ChannelId = channelId,
                Title = channelId,
                ThumbnailUrl = $"https://yt3.ggpht.com/ytc/{channelId}=s240-c-k-c0x00ffffff-no-rj"
            };
        }

        private async Task<ChannelIdentity?> TryOEmbedAsync(string youtubeUrl, string channelId)
        {
            try
            {
                var url =
                    $"https://www.youtube.com/oembed?url={youtubeUrl}&format=json";

                var json = await _http.GetStringAsync(url);

                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                var title = root.GetProperty("author_name").GetString();
                var thumb = root.GetProperty("thumbnail_url").GetString();

                if (string.IsNullOrWhiteSpace(title))
                    return null;

                return new ChannelIdentity
                {
                    ChannelId = channelId,
                    Title = title!,
                    ThumbnailUrl = thumb ?? ""
                };
            }
            catch
            {
                return null;
            }
        }
    }
}
