"""
SCRIPT: BlockGrower

THIS SCRIPT INCLUDES TWO ALGORITHMS - PATIENT AND GREEDY - FOR THE RANKING OF FARMLAND PARCELS BASED ON THEIR
STRATEGIC ATTRACTIVENESS FOR PRESERVATION. THE SCRIPT ALSO ALLOWS FOR SIMULATING PRESERVATION OUTCOMES IF THE
ALGORITHMS ARE FOLLOWED. PLEASE READ "ARCPY ALGORITHMS FOR STRATEGIC FARMLAND PRESERVATION" REPORT FOR MORE
INFORMATION.

To create an ArcToolbox tool with which to execute this script, do the following.
1   In  ArcMap > Catalog > Toolboxes > My Toolboxes, either select an existing toolbox
    or right-click on My Toolboxes and use New > Toolbox to create (then rename) a new one.
2   Drag (or use ArcToolbox > Add Toolbox to add) this toolbox to ArcToolbox.
3   Right-click on the toolbox in ArcToolbox, and use Add > Script to open a dialog box.
4   In this Add Script dialog box, use Label to name the tool being created, and press Next.
5   In a new dialog box, browse to the .py file to be invoked by this tool, and press Next.
6   In the next dialog box, specify the following inputs (using dropdown menus wherever possible)
    before pressing OK or Finish.
        DISPLAY NAME                    DATA TYPE           PROPERTY>DIRECTION>VALUE
        Parcels                         Feature Layer       Required>Input
        Status_Field                    Field               Required>Input
        Output_File                     Shapefile           Required>Output
        Deprioritize_Large_Blobs        Boolean             Optional>Input
        Method                          String              Required>Input>Filter:ValueList:"Greedy","Patient"
        Jump Distance                   Double              Required>Input
        Access Weight                   Double              Required>Input>Default:1
        Average Neighbor Size Weight    Double              Required>Input>Default:2
        Greedy Score Weight             Double              Required>Input>Default:4
        Averaging Iterations            Double              Required>Input>Default:3
        Greedy Score Weight             Double              Required>Input>Default:4
        Simulate                        Boolean             Required>Input
        Number of Simulations           Double              Required>Input>Default:1
        Parcels to Preserve             Double              Required>Input>Default:5

7   Additionally, include the following validation script in the Validation tab within the Properties Screen:
        def updateParameters(self):
            if self.params[4].value == "Patient":
                self.params[6].enabled = 1
                self.params[7].enabled = 1
                self.params[8].enabled = 1
                self.params[9].enabled = 1
            else:
                self.params[6].enabled = 0
                self.params[7].enabled = 0
                self.params[8].enabled = 0
                self.params[9].enabled = 0

            if self.params[10].value == True:
                self.params[11].enabled = 1
                self.params[12].enabled = 1
            else:
                self.params[11].enabled = 0
                self.params[12].enabled = 0

8       To later revise any of this, right-click to the tool's name and select Properties.
"""


# Import necessary modules
import sys, arcpy, traceback
import arcpy.cartography as CA

# Allow output file to overwrite any existing file of the same name
arcpy.env.overwriteOutput = True


def translate(value, oldMin, oldMax, newMin, newMax):
    ''' maps any value range to 1-100 range'''

    leftSpan = oldMax - oldMin
    rightSpan = newMax - newMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - oldMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return newMin + (valueScaled * rightSpan)


def preserve(ScoreField):
    '''Changes boolean "preservation status" of the parcels with the highest score'''

    arcpy.AddMessage("Preserving " + str(NumPreserve) + " Parcels")
    # list all scores and take the highest ones (based on user-specified number)
    FieldValues = arcpy.da.SearchCursor(UnpreservedParcels_Output, ScoreField)
    ValuesList = list(FieldValues)
    ValuesList = sorted(ValuesList, reverse=True)
    ToPreserve = ValuesList[NumPreserve][0]

    cur = arcpy.UpdateCursor(UnpreservedParcels_Output)
    Values = arcpy.SearchCursor(UnpreservedParcels_Output)
    CurrentRow = Values.next()

    # For each record, if the score is higher than the cutoff, set status field to 1
    for nextRecord in cur:
        Score = CurrentRow.getValue(ScoreField)
        if Score >= ToPreserve:
            nextRecord.setValue(StatusField, 1)
        cur.updateRow(nextRecord)
        # Move to next row in table
        CurrentRow = Values.next()

    # Delete row and update cursor objects to avoid locking attribute table
    del cur
    del CurrentRow


try:

    # obtain user input
    ParcelFeatures = arcpy.GetParameterAsText(0)
    arcpy.AddMessage('\n' + "Parcel shapefile: " + ParcelFeatures)

    StatusField = arcpy.GetParameterAsText(1)
    arcpy.AddMessage("The preservation status field is " + StatusField)

    UnpreservedParcels_Output = arcpy.GetParameterAsText(2)
    arcpy.AddMessage("The output shapefile name is " + UnpreservedParcels_Output)

    DePrioritizedChecked = arcpy.GetParameterAsText(3)

    Method = arcpy.GetParameterAsText(4)

    Jump = int(arcpy.GetParameterAsText(5))

    AccessWeight = int(arcpy.GetParameterAsText(6))

    AverageNeighbWeight = int(arcpy.GetParameterAsText(7))

    GreedyScoreWeight = int(arcpy.GetParameterAsText(8))

    AveragingIterations = int(arcpy.GetParameterAsText(9))

    simulate = arcpy.GetParameterAsText(10)

    NumSimulations = max(int(arcpy.GetParameterAsText(11)),1)

    NumPreserve = int(arcpy.GetParameterAsText(12))

    # if not simulating, only iterate over code once
    if str(simulate) != "true":
        NumSimulations = 1

    # begin counting number of times simulation has run
    simcount = 0

    # begin iterations
    for i in range(0,NumSimulations):

        # if currently in the middle of simulation. Set output layer from previous iteration to new input layer.
        if str(simulate) == "true" and simcount > 0:
            arcpy.AddMessage("Simulating iteration " + str(i+1))
            arcpy.DeleteField_management(UnpreservedParcels_Output, ['PatientScr','GreedyScr'])
            NewParcelFeatures = arcpy.CreateFeatureclass_management('in_memory', 'newparcels', 'POLYGON')
            arcpy.CopyFeatures_management(UnpreservedParcels_Output, NewParcelFeatures)
            arcpy.MakeFeatureLayer_management(NewParcelFeatures, 'ParcelLayer')

        # if not simulating or on first simulation iteration, use user-specified input layer
        elif str(simulate) == "true" and simcount == 0:
            arcpy.AddMessage("Simulating iteration " + str(i + 1))
            arcpy.MakeFeatureLayer_management(ParcelFeatures, 'ParcelLayer')

        else:
            arcpy.MakeFeatureLayer_management(ParcelFeatures, 'ParcelLayer')

        # create layers in memory as placeholder for output
        PreservedParcels = arcpy.CreateFeatureclass_management('in_memory', 'prsrvd', 'POLYGON')
        PreservedParcels_Output = arcpy.CreateFeatureclass_management('in_memory', 'prsrvdout', 'POLYGON')

        # separate preserved and unpreserved parcels for separate analyses
        arcpy.SelectLayerByAttribute_management('ParcelLayer', 'NEW_SELECTION', StatusField + " = 1")
        arcpy.CopyFeatures_management('ParcelLayer', PreservedParcels)

        arcpy.SelectLayerByAttribute_management('ParcelLayer', 'NEW_SELECTION', StatusField + " = 0")
        arcpy.CopyFeatures_management('ParcelLayer', UnpreservedParcels_Output)

        # calculate "blob" size of preserved parcels
        CA.AggregatePolygons(PreservedParcels, PreservedParcels_Output, Jump, "", "", "ORTHOGONAL", "", "")
        arcpy.AddGeometryAttributes_management(PreservedParcels_Output, "AREA", "", "ACRES")
        arcpy.AddGeometryAttributes_management(UnpreservedParcels_Output, "AREA", "", "ACRES")

        # set deprioritization factors if user chose to deprioritize large blobs
        if str(DePrioritizedChecked) == "true":
            factor500 = 0
            factor250 = 0.5
        else:
            factor500 = 1
            factor250 = 1

        # create new field to store blob size
        arcpy.AddField_management(PreservedParcels_Output, "WeightedAr", "FLOAT")

        # Create an enumeration of updatable records from the shapefile's attribute table
        cur = arcpy.UpdateCursor(PreservedParcels_Output)

        # Start cursor at the beginning of the attribute table
        Values = arcpy.SearchCursor(PreservedParcels_Output)
        CurrentRow = Values.next()

        # calculate blob size while taking into account the deprioritization factors
        for nextRecord in cur:
            CurrentValue = CurrentRow.getValue("POLY_AREA")
            if CurrentValue >= 500:
                nextRecord.setValue("WeightedAr", CurrentValue * factor500)
                cur.updateRow(nextRecord)
            elif CurrentValue >= 250 and CurrentValue < 500 >= 250:
                nextRecord.setValue("WeightedAr", CurrentValue * factor250)
                cur.updateRow(nextRecord)
            else:
                nextRecord.setValue("WeightedAr", CurrentValue)
                cur.updateRow(nextRecord)
            # Move to next row in table
            CurrentRow = Values.next()

        # Delete row and update cursor objects to avoid locking attribute table
        del cur
        del CurrentRow

        # create placeholder tables for upcoming calculations
        near_table = arcpy.management.CreateTable('in_memory', 'near_table')
        sum_table = arcpy.management.CreateTable('in_memory', 'sum_table')

        # calculate area sum of nearby preserved blobs for each unpreserved parcel.
        arcpy.GenerateNearTable_analysis(UnpreservedParcels_Output, PreservedParcels_Output, near_table, Jump, "", "", "ALL", "0", "PLANAR")
        arcpy.JoinField_management(near_table, "NEAR_FID", PreservedParcels_Output, "FID", "WeightedAr")
        arcpy.Statistics_analysis(near_table, sum_table, [["WeightedAr", "SUM"]], "IN_FID")
        arcpy.JoinField_management(UnpreservedParcels_Output, "FID", sum_table, "IN_FID", "SUM_WEIGHTEDAR")

        # combine the nearby blob area to the size of the unpreserved parcel and store in new combined acre field
        arcpy.AddField_management(UnpreservedParcels_Output, "CombndAcre", "FLOAT")
        arcpy.CalculateField_management(UnpreservedParcels_Output, "CombndAcre", "!SUM_WEIGHT! + !POLY_AREA!", "PYTHON_9.3","")

        # create "greedy weight" field to store upcoming information
        arcpy.AddField_management(UnpreservedParcels_Output, "GreedyWght", "FLOAT")

        cur = arcpy.UpdateCursor(UnpreservedParcels_Output)
        Values = arcpy.SearchCursor(UnpreservedParcels_Output)
        CurrentRow = Values.next()

        # loop through records and assign a "greedy weight" by adding the parcel's own value and the surrounding
        # "combined value".
        for nextRecord in cur:
            ParcelValue = CurrentRow.getValue("POLY_AREA")
            CombinedValue = CurrentRow.getValue("CombndAcre")
            SurroundingValue = CurrentRow.getValue("SUM_WEIGHT")
            if SurroundingValue == 0:
                nextRecord.setValue("GreedyWght", ParcelValue)
            else:
                nextRecord.setValue("GreedyWght", CombinedValue + ParcelValue)
            cur.updateRow(nextRecord)
            # Move to next row in table
            CurrentRow = Values.next()

        # only perform if method is set to greedy
        if Method == "Greedy":

            # create final "greedy score" field
            arcpy.AddField_management(UnpreservedParcels_Output, "GreedyScr", "INTEGER")

            # Delete row and update cursor objects to avoid locking attribute table
            del cur
            del CurrentRow

            FieldValues = arcpy.da.SearchCursor(UnpreservedParcels_Output, "GreedyWght")
            ValuesList = list(FieldValues)
            MaxSize = max(ValuesList)
            MinSize = min(ValuesList)

            cur = arcpy.UpdateCursor(UnpreservedParcels_Output)
            Values = arcpy.SearchCursor(UnpreservedParcels_Output)
            CurrentRow = Values.next()

            # loop through records and translate greedy weight to greedy score from 1-100
            for nextRecord in cur:
                WeightValue = CurrentRow.getValue("GreedyWght")
                NewValue = translate(WeightValue, MinSize[0], MaxSize[0], 1, 100)
                nextRecord.setValue("GreedyScr", NewValue)
                cur.updateRow(nextRecord)
                # Move to next row in table
                CurrentRow = Values.next()

            # Delete row and update cursor objects to avoid locking attribute table
            del cur
            del CurrentRow

            # if user chose to simulate, change preservation status of highest ranked parcels
            if str(simulate) == "true":
                preserve("GreedyScr")



        else:
            arcpy.AddMessage("This might take a while...")

            # create empty tables in memory for future calculations
            near_table2 = arcpy.management.CreateTable('in_memory', 'near_table2')
            sum_table2 = arcpy.management.CreateTable('in_memory', 'sum_table2')

            # calculate the total area to which each parcel has access (total area of neighboring parcels)
            arcpy.GenerateNearTable_analysis(UnpreservedParcels_Output, UnpreservedParcels_Output, near_table2, Jump, "", "", "ALL", "0", "PLANAR")
            arcpy.JoinField_management(near_table2, "NEAR_FID", UnpreservedParcels_Output, "FID", "POLY_AREA")
            arcpy.Statistics_analysis(near_table2, sum_table2, [["POLY_AREA", "SUM"],["NEAR_FID", "COUNT"]], "IN_FID")
            arcpy.JoinField_management(UnpreservedParcels_Output, "FID", sum_table2, "IN_FID", "SUM_POLY_AREA")
            arcpy.AddField_management(UnpreservedParcels_Output, "NeighbArea", "FLOAT")
            arcpy.CalculateField_management(UnpreservedParcels_Output, "NeighbArea", "!SUM_POLY_A!", "PYTHON_9.3", "")

            # calculate the average size of each parcel's neighboring parcels
            arcpy.JoinField_management(UnpreservedParcels_Output, "FID", sum_table2, "IN_FID", "COUNT_NEAR_FID")

            arcpy.AddField_management(UnpreservedParcels_Output, "AvgNeighSz", "FLOAT")
            arcpy.AddField_management(UnpreservedParcels_Output, "PatientWgt", "FLOAT")

            cur = arcpy.UpdateCursor(UnpreservedParcels_Output)
            Values = arcpy.SearchCursor(UnpreservedParcels_Output)
            CurrentRow = Values.next()

            for nextRecord in cur:
                SizeNeighbors = CurrentRow.getValue("NeighbArea")
                NumNeighbors = CurrentRow.getValue("COUNT_NEAR")
                if NumNeighbors == 0:
                    nextRecord.setValue("AvgNeighSz", 0)
                else:
                    nextRecord.setValue("AvgNeighSz", SizeNeighbors / NumNeighbors)

                Combined = CurrentRow.getValue("GreedyWght")
                AverageNeighbs = CurrentRow.getValue("AvgNeighSz")

                # set the patient weight value by adding all calculated score and weighing them by user specified amounts
                nextRecord.setValue("PatientWgt", (SizeNeighbors * AccessWeight) + (AverageNeighbs * AverageNeighbWeight) + (Combined * GreedyScoreWeight))
                cur.updateRow(nextRecord)
                CurrentRow = Values.next()

            # Delete row and update cursor objects to avoid locking attribute table
            del cur
            del CurrentRow

            # create empty tables in memory for future calculations
            near_table3 = arcpy.management.CreateTable('in_memory', 'near_table3')
            sum_table3 = arcpy.management.CreateTable('in_memory', 'sum_table3')

            arcpy.AddField_management(UnpreservedParcels_Output, "LocalValue", "FLOAT")

            # based on user-specified number of iterations, give each parcel the average patient weight of the surrounding parcels
            for i in range(AveragingIterations):
                arcpy.AddMessage("Averaging iteration " + str(i + 1))
                arcpy.GenerateNearTable_analysis(UnpreservedParcels_Output, UnpreservedParcels_Output, near_table3, Jump, "","", "ALL", "0", "PLANAR")
                arcpy.JoinField_management(near_table3, "NEAR_FID", UnpreservedParcels_Output, "FID", "PatientWgt")
                arcpy.Statistics_analysis(near_table3, sum_table3, [["PatientWgt", "MEAN"]], "IN_FID")
                arcpy.JoinField_management(UnpreservedParcels_Output, "FID", sum_table3, "IN_FID", "MEAN_PatientWgt")
                arcpy.CalculateField_management(UnpreservedParcels_Output, "PatientWgt", "(!MEAN_Patie!+!PatientWgt!)/2", "PYTHON_9.3", "")
                arcpy.DeleteField_management(UnpreservedParcels_Output, "MEAN_Patie")

                arcpy.CalculateField_management(UnpreservedParcels_Output, "LocalValue", "!LocalValue! + !PatientWgt!", "PYTHON_9.3", "")

            arcpy.AddField_management(UnpreservedParcels_Output, "PatientScr", "INTEGER")

            FieldValues = arcpy.da.SearchCursor(UnpreservedParcels_Output, "LocalValue")
            ValuesList = list(FieldValues)
            MaxSize = max(ValuesList)
            MinSize = min(ValuesList)

            cur = arcpy.UpdateCursor(UnpreservedParcels_Output)
            Values = arcpy.SearchCursor(UnpreservedParcels_Output)
            CurrentRow = Values.next()

            # Map each patient weight to a patient score from 1-100
            for nextRecord in cur:
                WeightValue = CurrentRow.getValue("LocalValue")
                NewValue = translate(WeightValue, MinSize[0], MaxSize[0], 1, 100)
                nextRecord.setValue("PatientScr", NewValue)
                cur.updateRow(nextRecord)
                # Move to next row in table
                CurrentRow = Values.next()

            # Delete row and update cursor objects to avoid locking attribute table
            del cur
            del CurrentRow

            # if user chose to simulate, change preservation status of highest ranked parcels
            if str(simulate) == "true":
                preserve("PatientScr")

        # delete all interim calculated fields
        arcpy.DeleteField_management(UnpreservedParcels_Output, ['LocalValue','PatientWgt','AvgNeighSz','COUNT_NEAR','NeighbArea','SUM_POLY_A','GreedyWght','CombndAcre','SUM_Weight','POLY_AREA'])

        # create a placeholder shapefile in memory and re-merge the preserved and unpreserved parcels
        UnpreservedPlaceholder = arcpy.CreateFeatureclass_management('in_memory', 'unprsrvdPH', 'POLYGON')
        arcpy.CopyFeatures_management(UnpreservedParcels_Output, UnpreservedPlaceholder)
        arcpy.Merge_management([UnpreservedPlaceholder, PreservedParcels], UnpreservedParcels_Output)

        # count the number of simulations
        simcount = simcount + 1

        # delete all items created in memory
        arcpy.Delete_management("in_memory")


    # Add a layer for that new shapefile to the active data frame
    currentMap = arcpy.mapping.MapDocument("CURRENT")
    currentDataFrame = currentMap.activeDataFrame
    layerToBeDisplayed = arcpy.mapping.Layer(UnpreservedParcels_Output)
    arcpy.mapping.AddLayer(currentDataFrame, layerToBeDisplayed, "TOP")
    del currentMap


except Exception as e:
    # If unsuccessful, end gracefully by indicating why
    arcpy.AddError('\n' + "Script failed because: \t\t" + e.message)
    # ... and where
    exceptionreport = sys.exc_info()[2]
    fullermessage = traceback.format_tb(exceptionreport)[0]
    arcpy.AddError("at this location: \n\n" + fullermessage + "\n")
