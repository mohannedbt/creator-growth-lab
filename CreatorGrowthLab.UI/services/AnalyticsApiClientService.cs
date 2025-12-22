using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Net;
using System.Text.Json;

using CreatorGrowthLab.UI.Models.Analytics;

namespace CreatorGrowthLab.UI.Services
{
    public class AnalyticsApiClientService
    {
        private readonly HttpClient _http;

        public AnalyticsApiClientService(HttpClient http)
        {
            _http = http;
        }

        public async Task<bool> HealthAsync(CancellationToken ct = default)
        {
            try
            {
                var resp = await _http.GetAsync("/health", ct);
                return resp.IsSuccessStatusCode;
            }
            catch
            {
                return false;
            }
        }

        public async Task<AnalyticsResponse?> AnalyzeChannelAsync(ChannelAnalysisRequest req, CancellationToken ct = default)
        {
            // FastAPI endpoint: POST /analyze/channel
            var resp = await _http.PostAsJsonAsync("/analyze/channel", req, ct);
            resp.EnsureSuccessStatusCode();
            return await resp.Content.ReadFromJsonAsync<AnalyticsResponse>(cancellationToken: ct);
        }
        

    public async Task<string> ResolveChannelIdAsync(string urlOrHandle, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(urlOrHandle))
            throw new ArgumentException("urlOrHandle cannot be empty.");

        var encoded = WebUtility.UrlEncode(urlOrHandle.Trim()); // encodes @ as %40
        var resp = await _http.GetAsync($"/resolve/channel-id?url_or_handle={encoded}", ct);
        resp.EnsureSuccessStatusCode();

        var json = await resp.Content.ReadAsStringAsync(ct);

        using var doc = JsonDocument.Parse(json);

        // expected: { "channel_id": "UC..." }
        if (doc.RootElement.TryGetProperty("channel_id", out var v1))
            return v1.GetString() ?? "";

        // fallback if you ever return different key casing
        if (doc.RootElement.TryGetProperty("channelId", out var v2))
            return v2.GetString() ?? "";

        throw new InvalidOperationException("Resolve endpoint returned unexpected JSON. Expected { channel_id: 'UC...' }");
    }
    }
}
