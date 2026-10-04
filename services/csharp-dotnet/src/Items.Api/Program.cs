using Items.Api;

WebApplication app = AppComposition.Build(args);
await AppComposition.WarmPoolAsync(app);
await app.RunAsync();

/// <summary>Makes the entry point visible to WebApplicationFactory in the integration tests.</summary>
public partial class Program;
