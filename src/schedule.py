import pandas as pd
import numpy as np
from tabulate import tabulate


EIGHTH_GRADE_WORKSHOP_SESSION = 1 #TODO: 8TH GRADE DISCUSSION SECTION, 4TH FLOOR NORTH

WORKSHOP_NUM_SESSIONS = 3
NUMBER_OF_PREFERENCES = 5
NUMBER_OF_PREFERENCES_LIST = range(1, NUMBER_OF_PREFERENCES + 1)
WORKSHOP_PREFERENCES_HEADERS = []
for num in NUMBER_OF_PREFERENCES_LIST:
    WORKSHOP_PREFERENCES_HEADERS.append(f'Workshop {num}')

WORKSHOP_SESSION_HEADERS = []
for num in range(1, WORKSHOP_NUM_SESSIONS + 1):
    WORKSHOP_SESSION_HEADERS.append(f'Session {num}')

def import_student_preferences(students_file):
    students_df = pd.read_csv(students_file, sep='\t')
    return students_df

def import_workshop_df(workshop_file):
    workshop = pd.read_csv(workshop_file, sep='\t')
    return workshop

#go through each col that represents an individual workshop
#for each col,
#if there is a value that starts with a number in the preference range,
#place that column's name in the cell for that person's row
#for instance, if it finds "1st Choice" in a column for Queer Joy workshop,
#then add that to that row, but in the "Preference 1" column for the given student
def convert_workshop_pref_columns(student_preference_df, workshop_df):
    student_preference_df_final = student_preference_df

    workshop_pref_cols = [col for col in student_preference_df_final if col.startswith("Workshop Preferences")]

    student_preference_df_final = student_preference_df_final.replace(to_replace=r'(st|nd|rd|th) Choice', value="", regex=True)
    student_preference_df_final.fillna(0, inplace=True)
    student_preference_df_final[workshop_pref_cols] = student_preference_df_final[workshop_pref_cols].astype("int8")
    # replace the rest with zeroes


    for pref in range(1, NUMBER_OF_PREFERENCES + 1):
        student_preference_df_final[f"Preference {pref}"] = student_preference_df_final[workshop_pref_cols].apply(
            lambda row: row[row == pref].index[0] if len(row[row == pref]) > 0 else "None", axis=1)


    student_preference_df_final = student_preference_df_final.drop(columns=workshop_pref_cols)
    # lastly, turn all names into their actual workshop names
    student_preference_df_final = student_preference_df_final.replace(to_replace=r"Workshop Preferences \[", value="", regex=True)
    student_preference_df_final = student_preference_df_final.replace(to_replace=r"\]", value="", regex=True)
    # validate all names against the workshop dict
    # for header in WORKSHOP_SESSION_HEADERS:
    #     frame1 = student_preference_df_final[header]
    #     frame2 = workshop_df['Name']
    #     diff = frame2[~frame2.isin(frame1)].values
    #     if len(diff) > 0:
    #         raise Exception("Name mismatch")

    return student_preference_df_final


# arguments: student_preference_df, workshop_df
# returns a dataframe of students and workshop placements, and a workshop df of attendance and max capacities
# student df
# name // email // grade // Workshop 1 // Workshop 2
# workshop df
# Name // Location // Attendance Count // Capacity
def schedule_students(student_preference_df, workshop_df):
    student_placements = student_preference_df[['Name', 'Email', 'Grade']]
    student_placements.set_index('Email', inplace=True)
    student_placements[WORKSHOP_PREFERENCES_HEADERS] = "Unscheduled"
    workshop_enrollments = workshop_df[['Name', 'Location', 'Capacity']]
    workshop_enrollments['Attendance Count'] = 0

    workshop_names = workshop_df["Name"].array
    # for each preference level
    for pref in NUMBER_OF_PREFERENCES_LIST:
        # for each workshop, get a list of students who put it at that preference level
        for workshop in workshop_names:
            students_who_want_workshop = student_preference_df[student_preference_df[
                                                                   f'Workshop Preference {pref}'] == workshop]
            sessions = workshop_df.iloc['Name' == workshop]['Availability'].split(',')
            for session in sessions:
                # merge current scheduled students with students_available_df, merge on email
                # use this dataframe to pull students who are unscheduled for that session
                students_available_for_workshop = pd.merge(students_who_want_workshop, student_placements,
                                                           on='Email', how='left')
                students_available_for_workshop = students_available_for_workshop.apply(
                    lambda row: row[f"Session {session}"] == 'None' and row[[WORKSHOP_SESSION_HEADERS]] != workshop
                    , axis=1)

                # sample students based on current attendance
                students_selected = students_available_for_workshop.sample(
                    n=(workshop_enrollments.loc[workshop]['Max Attendance'] -
                       workshop_enrollments.loc[workshop]['Attendance Count']) / 1, axis=0)

                # schedule students and update student_placements accordingly
                # locate each student in student_placements, add the workshop name to the Session n column
                students_selected[f'Session {session}'] = workshop
                student_placements = pd.merge(student_placements, students_selected,
                                              on=f'Session {session}', how='inner')
                workshop_enrollments['Attendance Count'][f"Session {session}"] += len(students_selected)

    return student_placements, workshop_enrollments

def main():
    workshop_df = import_workshop_df('./data/workshop_data.tsv')
    student_df = import_student_preferences('./data/student_preferences.tsv')
    student_df = convert_workshop_pref_columns(student_df, workshop_df)
    student_placements, workshop_enrollments = schedule_students(student_df, workshop_df)
    print

if __name__ == '__main__':
    main()