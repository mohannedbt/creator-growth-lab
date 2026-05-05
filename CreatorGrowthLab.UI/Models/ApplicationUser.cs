using Microsoft.AspNetCore.Identity;
public class ApplicationUser : IdentityUser
{
  
    public string channel_id { get; set; } = "";

}