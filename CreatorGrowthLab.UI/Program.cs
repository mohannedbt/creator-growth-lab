using CreatorGrowthLab.UI.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllersWithViews();

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

app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Dashboard}/{action=Index}/{id?}");

app.Run();
