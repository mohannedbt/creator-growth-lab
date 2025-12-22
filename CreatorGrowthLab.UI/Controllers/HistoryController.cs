using System.Threading;
using System.Threading.Tasks;
using CreatorGrowthLab.UI.Controllers;
using CreatorGrowthLab.UI.Services;
using Microsoft.AspNetCore.Mvc;
using CreatorGrowthLab.UI.Models.Analytics;

namespace CreatorGrowthLab.UI.Controllers
{
    public class HistoryController : Controller
    {
        private readonly AnalyticsRunStore _runs;

        public HistoryController(AnalyticsRunStore runs)
        {
            _runs = runs;
        }

        [HttpGet]
        public async Task<IActionResult> Index(CancellationToken ct)
        {
            var vm = new HistoryViewModel
            {
                Runs = await _runs.ListRunsAsync(ct)
            };
            return View(vm);
        }

        // Open a saved run and show it using the Dashboard view (reusing the UI)
        [HttpGet]
        public async Task<IActionResult> Open(string file, CancellationToken ct)
        {
            var resp = await _runs.ReadRunAsync(file, ct);
            if (resp == null) return NotFound("Run file not found.");

            // reuse dashboard view model
            var vm = new DashboardViewModel
            {
                Request = new ChannelAnalysisRequest
                {
                    ChannelId = resp.Meta.ChannelId,
                    NVideos = resp.Meta.NVideos,
                    BaselineWindow = resp.Meta.BaselineWindow
                },
                Response = resp
            };

            // This run is local, so API health isn't relevant
            ViewBag.ApiHealthy = false;

            return View("~/Views/Dashboard/Index.cshtml", vm);
        }
    }

    public class HistoryViewModel
    {
        public System.Collections.Generic.List<RunListItem> Runs { get; set; } =
            new System.Collections.Generic.List<RunListItem>();
    }
}
