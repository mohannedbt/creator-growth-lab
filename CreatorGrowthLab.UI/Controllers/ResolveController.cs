using System;
using System.Threading;
using System.Threading.Tasks;
using CreatorGrowthLab.UI.Services;
using Microsoft.AspNetCore.Mvc;

namespace CreatorGrowthLab.UI.Controllers
{
    public class ResolveController : Controller
    {
        private readonly AnalyticsApiClientService _api;

        public ResolveController(AnalyticsApiClientService api)
        {
            _api = api;
        }

        [HttpGet]
        public IActionResult Index(string? input = null)
        {
            return View(new ResolveViewModel { Input = input ?? "" });
        }

        [HttpPost]
        [ValidateAntiForgeryToken]
        public async Task<IActionResult> Index(ResolveViewModel vm, CancellationToken ct)
        {
            if (string.IsNullOrWhiteSpace(vm.Input))
            {
                vm.ErrorMessage = "Please enter a YouTube handle like @Khyo or a channel URL.";
                return View(vm);
            }

            try
            {
                vm.ChannelId = await _api.ResolveChannelIdAsync(vm.Input, ct);
                if (string.IsNullOrWhiteSpace(vm.ChannelId) || !vm.ChannelId.StartsWith("UC"))
                    vm.ErrorMessage = "Resolve succeeded but returned an invalid channel id.";
            }
            catch (Exception ex)
            {
                vm.ErrorMessage = $"Resolve failed: {ex.Message}";
            }

            return View(vm);
        }
    }

    public class ResolveViewModel
    {
        public string Input { get; set; } = "";
        public string? ChannelId { get; set; }
        public string? ErrorMessage { get; set; }
    }
}
