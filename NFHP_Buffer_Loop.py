import subprocess

NHDPlusList = ("02") #, "14", "15", "16", "17", "18") #, "10l") #, "13", "14", "15", "16", "17", "18") # 10u, 10l

for NHDPlus in NHDPlusList :
    subprocess.call([r"C:\Python26\ArcGIS10.0\python",
                     r"NFHP_Buffers.py",
                     NHDPlus,
                     ])

