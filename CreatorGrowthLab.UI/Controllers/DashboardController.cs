using System;
using System.Threading;
using System.Threading.Tasks;
using CreatorGrowthLab.UI.Models.Analytics;
using CreatorGrowthLab.UI.Services;
using Microsoft.AspNetCore.Mvc;

namespace CreatorGrowthLab.UI.Controllers
{
    public class DashboardController : Controller
    {
        private readonly AnalyticsApiClientService _api;

        public DashboardController(
            AnalyticsApiClientService api
            )
        {
            _api = api;
        }

        [HttpGet]
        public async Task<IActionResult> Index(string? channelId, CancellationToken ct)
        {
            ViewBag.ApiHealthy = await _api.HealthAsync(ct);

            var vm = new DashboardViewModel
            {
                IsReadOnly = false
            };

            if (!string.IsNullOrWhiteSpace(channelId))
                vm.Request.ChannelId = channelId;

            return View(vm);
        }

        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Analyze(DashboardViewModel vm, CancellationToken ct)
        {
            ViewBag.ApiHealthy = await _api.HealthAsync(ct);

            if (vm.IsReadOnly)
                return BadRequest("Read-only dashboard");

            if (string.IsNullOrWhiteSpace(vm.Request.ChannelId))
            {
                vm.ErrorMessage = "ChannelId is required (starts with UC...).";
                return View("Index", vm);
            }

            try
            {
                // 🔥 Single source of truth
                vm.Response = await _api.AnalyzeChannelAsync(vm.Request, ct);

            }
            catch (Exception ex)
            {
                vm.ErrorMessage = $"API error: {ex.Message}";
            }

            return View("Index", vm);
        }
    }
public class DashboardViewModel
{
    public ChannelAnalysisRequest Request { get; set; } = new();
    public AnalyticsResponse? Response { get; set; }

    public ChannelIdentity? Channel => Response?.Channel;

    public bool IsReadOnly { get; set; } = false;
    public string? ErrorMessage { get; set; }
}

}
