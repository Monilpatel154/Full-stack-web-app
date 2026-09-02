import os
import re

site_dir = r"m:/LADLI 101/LADLI_visitor-management_fixed/site"
admin_dir = r"m:/LADLI 101/LADLI_visitor-management_fixed/admin"

dirs = [site_dir, admin_dir]

html_files = []
for d in dirs:
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith('.html'):
                html_files.append(os.path.join(root, f))

print(f"Found {len(html_files)} HTML files.")

target_block = '''    <meta name="viewport" content="width=1280, initial-scale=1, minimum-scale=0.25, maximum-scale=5.0, user-scalable=yes" />
    <script>
      (function(){
        var w=1280;
        function fitVP(){
          var vp=document.querySelector('meta[name="viewport"]');
          if(!vp){vp=document.createElement('meta');vp.name='viewport';document.head.appendChild(vp);}
          var sw=window.innerWidth||(window.screen&&window.screen.width)||w;
          if(sw<w){
            var s=sw/w;
            vp.setAttribute('content','width='+w+',initial-scale='+s+',minimum-scale='+(s*0.3)+',maximum-scale=3.0,user-scalable=yes');
          }else{
            vp.setAttribute('content','width=1280,initial-scale=1.0,maximum-scale=3.0,user-scalable=yes');
          }
        }
        fitVP();
        window.addEventListener('resize',fitVP);
        window.addEventListener('orientationchange',fitVP);
      })();
    </script>'''

# Regex to find meta viewport and any previous inline scaler
pattern = re.compile(
    r'<meta\s+name=["\']viewport["\'][^>]*>(?:\s*<script>[\s\S]*?fitVP[\s\S]*?</script>|\s*<script>[\s\S]*?var w=1280[\s\S]*?</script>)?',
    re.IGNORECASE
)

updated_count = 0
for file_path in html_files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = pattern.sub(target_block, content)
    
    if new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        updated_count += 1
        print(f"Updated: {os.path.basename(file_path)}")

print(f"Successfully updated {updated_count} files.")
