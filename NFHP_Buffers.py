import arcpy
from arcpy import env
from arcpy.sa import *
import sys

# Input NHDPlus region below or alternatively use the commented code when running with NFHP_loop.py for multiple regions
NHDPlus = "02" #sys.argv[1]

print "Running region" + NHDPlus

# Provide workspace
arcpy.env.workspace  = r"C:/NFHAP/Buffers/NHDPlus" + NHDPlus

NHDSource      = r"E:/NFHI/NHDPlus/NHDPlus" + NHDPlus # Path to NHDPlus data
boundaryRaster = NHDSource + "/Drainage/cat"
boundaryPoly   = NHDSource + "/Drainage/catchment_dissolve.shp"
NHDwb          = r"C:/NFHAP/Buffers/NHDPlus_waterbodies_merge.shp"

# Output files
NHDStream        = "nhdflowline_albers.shp"
NHDStreamTable   = "nhdflowline_albers.dbf"
NHDArea          = "NHDArea_albers.shp"
NHDLake1         = "NHD_Lakepond_Reservoir.shp"
NHDLake2         = "NHD_Lakepond_Reservoir_albers.shp"
rapidsArea       = "rapids_area_albers.shp"
streamArea       = "stream_area_albers.shp"
finalArea        = "final_area_albers.shp"
streaminAreaTemp = "flowlines_in_area_temp_albers.shp"
streaminArea     = "flowlines_in_area_albers.shp"
streamRaster     = "nhdstrm"
strminArea       = "nhdstrma"
nhdarea          = "nhdarea"
nhdlake          = "nhdlake"
costarea         = "costarea"
costalloc        = "costalloc"
mergeRaster      = "nhdmerge"
mergeArea        = "rivlkmerge"
# Query expressions
expression1      = '"FCODE" = 43100'
expression2      = '"nhdflowline_albers.COMID" > 0'
expression3      = '"NHDArea_albers.FCODE" = 46006 or "NHDArea_albers.FCODE" = 33600 or "NHDArea_albers.FCODE" = 53700'
expression4      = '"FTYPE_1" <> \'Coastline\''

layerlist = ("NHDwb_National", "StreamLines", "StreamArea", "Lakes", "StreamInAreaTemp",
            "NHD_Lakepond_Reservoir.shp", NHDStream, NHDArea, NHDLake1, NHDLake2,rapidsArea, streamArea, streaminAreaTemp,
            finalArea, streaminArea, streamRaster, strminArea, nhdarea, nhdlake, costarea, costalloc, mergeRaster, mergeArea,
            "buff30", "buff60", "buff90", "buff30f", "buff60f", "buff90f")

for layer in layerlist:
    if arcpy.Exists(layer):
        arcpy.Delete_management(layer)

## Convert national lake shapefile to a layer
print "Making national waterbody feature layer"
arcpy.MakeFeatureLayer_management (NHDwb, "NHDwb_National")

## Select lake and reservoirs from national shapefile
print "Selecting lakes and reservoirs"
arcpy.SelectLayerByLocation_management("NHDwb_National", "INTERSECT", boundaryPoly)
arcpy.CopyFeatures_management("NHDwb_National", NHDLake1)

## Reproject NHDPlus datasets into Albers"
fcList = ("nhdflowline", "NHDArea", "NHD_Lakepond_Reservoir") 
for fc in fcList:
    message = "Projecting" + " " + fc
    print  message

    infc = fc + ".shp"
    outfc = fc + "_albers.shp"

    arcpy.Project_management(infc, outfc, "C:/NFHAP/Buffers/Albers.prj")

## Convert shapefiles to feature layers
print "Making feature layers"
arcpy.MakeFeatureLayer_management (NHDStream, "StreamLines")
arcpy.MakeFeatureLayer_management (NHDArea, "StreamArea")
arcpy.MakeFeatureLayer_management (NHDLake1, "Lakes")

## Identify NHDArea polygons
# Select "Rapids" feature type from NHDArea
print "Selecting Rapids feature type from NHDArea polygons"
arcpy.Select_analysis("StreamArea", rapidsArea, expression1)

print "Selecting additional NHDArea polygons"
# Join the nhdflowline table to the NHDArea feature layer to identify NHDArea features with flowlines within them
arcpy.AddJoin_management("StreamArea", "COMID", NHDStreamTable, "WBAREACOMI")   
# Select desired features 
arcpy.SelectLayerByAttribute_management("StreamArea", "NEW_SELECTION", expression2)
arcpy.SelectLayerByAttribute_management("StreamArea", "SUBSET_SELECTION", expression3)
# Copy the layer to a new permanent feature class
arcpy.CopyFeatures_management("StreamArea", streamArea)

print "Creating final NHD area polygons"
arcpy.Merge_management([rapidsArea, streamArea], finalArea, "#")
inFeatures = [finalArea, "StreamLines"]

## Identify nhdflowlines within NHDArea polygons
print "Intersecting nhdflowlines with NHD area polygons"
arcpy.Intersect_analysis([finalArea, NHDStream], streaminAreaTemp, "#", "#", "line")
# Remove coastline arcs
arcpy.MakeFeatureLayer_management (streaminAreaTemp, "StreamInAreaTemp")                         
arcpy.SelectLayerByAttribute_management("StreamInAreaTemp", "NEW_SELECTION", expression4)
arcpy.CopyFeatures_management("StreamInAreaTemp", streaminArea)

ext = Raster(boundaryRaster).extent
arcpy.env.extent = ext
arcpy.CheckOutExtension("Spatial")

## Convert shapefiles/layers to 30m rasters
arcpy.PolylineToRaster_conversion(NHDStream, "BUFFID", streamRaster, "MAXIMUM_LENGTH", "NONE", 30)
print "NHDStream to raster"
arcpy.PolylineToRaster_conversion(streaminArea, "BUFFID", strminArea, "MAXIMUM_LENGTH", "NONE", 30)
arcpy.BuildRasterAttributeTable_management(strminArea, "Overwrite")
print "streaminNHDArea to raster"
arcpy.PolygonToRaster_conversion(finalArea, "FID", nhdarea, "CELL_CENTER", "",  30)
print "NHDArea to raster"
arcpy.PolygonToRaster_conversion(NHDLake2, "BUFFID", nhdlake, "CELL_CENTER", "",  30)
print "NHD Waterbodies to raster"

## Run cost allocation function to assign reach ID values to NHDArea river polygons
costArea = Con(nhdarea, 1, "", "VALUE > -1")
costArea.save(costarea)
print "Created cost area"
costAllocOut = CostAllocation(strminArea, costarea, "", "", "", "", "")
costAllocOut.save(costalloc)
print "Creation cost allocation grid"

## Grid merge of raster streams, rivers, and lakes to be used as buffer "seed"
arcpy.MosaicToNewRaster_management(streamRaster + ";" + nhdlake + ";" + costalloc, env.workspace, mergeRaster,
                                   '#', "16_BIT_UNSIGNED", 30, 1, "FIRST","FIRST")

arcpy.BuildRasterAttributeTable_management(mergeRaster, "Overwrite")

arcpy.MosaicToNewRaster_management(nhdlake + ";" + costalloc, env.workspace, mergeArea,
                                   '#', "16_BIT_UNSIGNED", 30, 1, "FIRST","FIRST")
                    
print "Grid merge of streams/rivers/lakes created"

## Buffer 30, 60, and 90 meters on each side of stream/river/lake                        
eucAllocate1 = EucAllocation(mergeRaster, 30, "", 30)
eucAllocate1.save("buff30")
print "30 meter buffer created"

eucAllocate2 = EucAllocation(mergeRaster, 60, "", 30)
eucAllocate2.save("buff60")
print "60 meter buffer created"

eucAllocate3 = EucAllocation(mergeRaster, 90, "", 30)
eucAllocate3.save("buff90")
print "90 meter buffer created"

## Create Mask Grid
print "Creating mask grid"
maskGrid = Con(IsNull(mergeArea), 1, "", "VALUE > 0")
maskGrid.save("mask_rivlk")

removeArea1 = Con(boundaryRaster, 1, "", "VALUE > 0")
removeArea1.save("mask_elev")

removeArea2 = Con(Raster("mask_rivlk") + Raster("mask_elev"), 2, "", "VALUE = 2")
removeArea2.save("mask_final")

## Execute ExtractByMask
print "Clipping by elevation grid"                        
outExtractByMask1 = ExtractByMask("buff30", "mask_final")
outExtractByMask1.save("buff30f") 
print "30 meter finished"
print "Clipping by elevation grid"                        
outExtractByMask2 = ExtractByMask("buff60", "mask_final")
outExtractByMask2.save("buff60f")
print "60 meter finished"
print "Clipping by elevation grid"                        
outExtractByMask3 = ExtractByMask("buff90", "mask_final")
outExtractByMask3.save("buff90f")
print "90 meter finished"                 

## Convert raster buffer to polygon
print "Converting raster buffers to polygons:"
arcpy.RasterToPolygon_conversion("buff30f", "buff30f.shp", "NO_SIMPLIFY", "VALUE")
print "30 meter finished"
arcpy.RasterToPolygon_conversion("buff60f", "buff60f.shp", "NO_SIMPLIFY", "VALUE")
print "60 meter finished"
arcpy.RasterToPolygon_conversion("buff90f", "buff90f.shp", "NO_SIMPLIFY", "VALUE")
print "90 meter finished"

## Create buffer polygon feature layers
print "Making buffer polygon feature layers"
arcpy.MakeFeatureLayer_management ("buff30f.shp", "buff30f")
arcpy.MakeFeatureLayer_management ("buff60f.shp", "buff60f")
arcpy.MakeFeatureLayer_management ("buff90f.shp", "buff90f")

## Dissolve polygon buffers using unique ID
print "Dissolving vector buffers:"
arcpy.Dissolve_management("buff30f", "buff30f_dissolve.shp", "GRIDCODE", "", 
                      "MULTI_PART", "")
print "30 meter finished"
arcpy.Dissolve_management("buff60f", "buff60f_dissolve.shp", "GRIDCODE", "", 
                      "MULTI_PART", "")
print "60 meter finished"
arcpy.Dissolve_management("buff90f", "buff90f_dissolve.shp", "GRIDCODE", "", 
                      "MULTI_PART", "")                     
print "90 meter finished"

## Add/calculate area
print "Calculating buffer areas"
calc_exp = "(float(!SHAPE.AREA!)) / 1000000"
arcpy.AddField_management("buff30f_dissolve.shp", "Buff30_km2", "Double", 12, 3)
arcpy.CalculateField_management("buff30f_dissolve.shp", "Buff30_km2", calc_exp, "PYTHON")

arcpy.AddField_management("buff60f_dissolve.shp", "Buff60_km2", "Double", 12, 3)
arcpy.CalculateField_management("buff60f_dissolve.shp", "Buff60_km2", calc_exp, "PYTHON")

arcpy.AddField_management("buff90f_dissolve.shp", "Buff90_km2", "Double", 12, 3)
arcpy.CalculateField_management("buff90f_dissolve.shp", "Buff90_km2", calc_exp, "PYTHON")
                     
## Delete Temporary Files
arcpy.DeleteFeatures_management(streaminAreaTemp)                         

print "Finished buffers for region NHDPlus" + NHDPlus

