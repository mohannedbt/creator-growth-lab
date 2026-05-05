using CreatorGrowthLab.UI.Services;
using CreatorGrowthLab.UI.Models;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllersWithViews();

// --------------------
// SQLite + EF Core
// --------------------
var conn = builder.Configuration.GetConnectionString("Default") ?? "Data Source=app.db";

builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlite(conn));

// --------------------
// Identity (cookie auth)
// --------------------
builder.Services
    .AddIdentity<ApplicationUser, IdentityRole>(options =>
    {
        // Optional: tweak password rules for dev
        options.Password.RequireNonAlphanumeric = false;
        options.Password.RequireUppercase = false;
        options.Password.RequireLowercase = false;
        options.Password.RequireDigit = false;
        options.Password.RequiredLength = 6;
    })
    .AddEntityFrameworkStores<AppDbContext>()
    .AddDefaultTokenProviders();

// Optional: configure cookie paths
builder.Services.ConfigureApplicationCookie(options =>
{
    options.LoginPath = "/Account/Login";
    options.AccessDeniedPath = "/Account/AccessDenied";
});

// --------------------
// Your API clients/services
// --------------------
var baseUrl = builder.Configuration["AnalyticsApi:BaseUrl"] ?? "http://127.0.0.1:8000";

builder.Services.AddHttpClient<AnalyticsApiClientService>(http =>
{
    http.BaseAddress = new Uri(baseUrl);
    http.Timeout = TimeSpan.FromSeconds(60);
});

builder.Services.AddSingleton<AnalyticsRunStore>();
builder.Services.AddHttpClient<YouTubeChannelService>();

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();

app.UseRouting();

// ✅ must be between UseRouting and MapControllerRoute
app.UseAuthentication();
app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

app.Run();
