import zipfile
import os

with zipfile.ZipFile('../sample-repo.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('.'):
        for f in files:
            fp = os.path.join(root, f)
            arcname = fp[2:] if fp.startswith('./') else fp
            z.write(fp, arcname)

print("Created sample-repo.zip")