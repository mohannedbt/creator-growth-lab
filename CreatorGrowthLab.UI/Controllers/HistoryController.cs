using CreatorGrowthLab.UI.Models.Analytics;
using CreatorGrowthLab.UI.Services;
using Microsoft.AspNetCore.Mvc;

namespace CreatorGrowthLab.UI.Controllers
{
    public class HistoryController : Controller
    {
        private readonly AnalyticsRunStore _store;

        public HistoryController(AnalyticsRunStore store)
        {
            _store = store;
        }

        // History list
        [HttpGet]
        public async Task<IActionResult> Index()
        {
            var runs = await _store.ListRunsAsync();
            return View(runs);
        }

        // View a past run using the Dashboard UI
        [HttpGet]
        public async Task<IActionResult> ViewBoard(string id)
        {
            if (string.IsNullOrWhiteSpace(id))
                return NotFound();

            var run = await _store.ReadRunAsync(id);
            if (run == null)
                return NotFound();

            var vm = new DashboardViewModel
            {
                Request = new ChannelAnalysisRequest
                {
                    ChannelId = run.Meta.ChannelId,
                    NVideos = run.Meta.NVideos,
                    BaselineWindow = run.Meta.BaselineWindow
                },
                Response = run,
                IsReadOnly = true
                // ❌ NO YouTube call
                // ✅ Channel comes from run.Channel
            };

            return View("~/Views/Dashboard/Index.cshtml", vm);
        }
    }
}
