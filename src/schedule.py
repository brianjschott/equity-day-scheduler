import pandas as pd

#TODO: Change the scheduling to use the 8th grade session column, schedule
# 8th graders for Session 1
GRADE_8_WORKSHOP = {
    "name": "Eighth Grade Discussion",
    "session": 1,
    "location": "4th Floor North"
}

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
    students_df = pd.read_csv(students_file, sep='\t', dtype={'Grade': 'int8'})
    return students_df


def import_workshop_df(workshop_file):
    workshop = pd.read_csv(workshop_file, sep='\t')
    workshop['Max Attendance'] = workshop['Max Attendance'].fillna(16)
    return workshop


def import_student_facilitator_df(facilitator_filepath):
    return pd.read_csv(facilitator_filepath, sep='\t')


# go through each col that represents an individual workshop
# for each col,
# if there is a value that starts with a number in the preference range,
# place that column's name in the cell for that person's row
# for instance, if it finds "1st Choice" in a column for Queer Joy workshop,
# then add that to that row, but in the "Preference 1" column for the given student
def convert_workshop_pref_columns(student_preference_df, workshop_df):
    student_preference_df_final = student_preference_df

    workshop_pref_cols = [col for col in student_preference_df_final if col.startswith("Workshop Preferences")]

    student_preference_df_final = student_preference_df_final.replace(to_replace=r'(st|nd|rd|th) Choice', value="",
                                                                      regex=True)
    student_preference_df_final.fillna(0, inplace=True)
    student_preference_df_final[workshop_pref_cols] = student_preference_df_final[workshop_pref_cols].astype("int8")

    # replace the rest with zeroes
    for pref in range(1, NUMBER_OF_PREFERENCES + 1):
        student_preference_df_final[f"Preference {pref}"] = student_preference_df_final[workshop_pref_cols].apply(
            lambda row: row[row == pref].index[0] if len(row[row == pref]) > 0 else "None", axis=1)

    student_preference_df_final = student_preference_df_final.drop(columns=workshop_pref_cols)
    # lastly, turn all names into their actual workshop names
    student_preference_df_final = student_preference_df_final.replace(to_replace=r"Workshop Preferences \[", value="",
                                                                      regex=True)
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
    student_placements[WORKSHOP_SESSION_HEADERS] = "Unscheduled"
    workshop_enrollments = workshop_df[['Name', 'Location', 'Max Attendance']]
    for i in range(1, WORKSHOP_NUM_SESSIONS + 1):
        workshop_enrollments.loc[:, f'Attendance Count Session {i}'] = 0

    workshop_names = workshop_df["Name"].array
    # for each preference level
    for pref in NUMBER_OF_PREFERENCES_LIST:
        # for each workshop, get a list of students who put it at that preference level
        for workshop in workshop_names:
            students_who_want_workshop = student_preference_df[student_preference_df[
                                                                   f'Preference {pref}'] == workshop]
            sessions = workshop_df.loc[workshop_df['Name'] == workshop, 'Availability'].values[0].split(',')
            for session in sessions:
                # merge current scheduled students with students_available_df, merge on email
                # use this dataframe to pull students who are unscheduled for that session
                data = pd.merge(students_who_want_workshop, student_placements,
                                on='Email', how='left', suffixes=('', '_y'))
                data = data.loc[:, ~data.columns.str.endswith('_y')]  # drops repeat cols on merge
                students_available_for_workshop = data[(data[f"Session {session}"] == 'Unscheduled')]
                # eliminates students who are already scheduled for workshop
                students_available_for_workshop = students_available_for_workshop[
                    (students_available_for_workshop[WORKSHOP_SESSION_HEADERS] != workshop).all(axis=1)]
                a = workshop_enrollments.loc[workshop_enrollments['Name'] == workshop, 'Max Attendance'].values[0]
                b = workshop_enrollments.loc[
                    workshop_enrollments['Name'] == workshop, f'Attendance Count Session {session}'].values[0]
                # sample students based on current attendance
                if (a - b) > 0:
                    students_selected = students_available_for_workshop.sample(
                        n=min(int(a - b), len(students_available_for_workshop)), axis=0)

                    # schedule students and update student_placements accordingly
                    # locate each student in student_placements, add the workshop name to the Session n column
                    student_placements.loc[students_selected["Email"], f"Session {session}"] = workshop
                    # drop_y(rename_x(
                    workshop_enrollments.loc[
                        workshop_enrollments['Name'] == workshop, f'Attendance Count Session {session}'] += len(
                        students_selected)
    return student_placements, workshop_enrollments


# anyone who is an 8th grader gets a discussion section at that period
def schedule_eighth_grade_discussion(student_df, grade_8_workshop):
    student_df.loc[student_df['Grade'] == 8, f"Session {grade_8_workshop.session}"] = grade_8_workshop.name
    return student_df


# schedules workshop moderators into their designated sessions
# spreadsheet lists name, email, workshop, and sessions
# returns student df, workshop_df not necessary because these students don't
# count for attendance purposes
def schedule_workshop_facilitators(student_df, student_facilitators_df):
    student_df = student_df.apply(
        lambda row: add_facilitator_to_workshop(row, student_facilitators_df.loc[row["Name"], "Sessions"]))
    return student_df


def add_facilitator_to_workshop(row, workshop_name):
    # get availability from row, convert to array
    session_list = row["Availability"].array
    for session in session_list:
        row[f"Session {session}"] = workshop_name
    return row


# takes student_df and exclusions_df
# changes all instances of workshop preferences
def erase_ineligible_student_prefs(student_df, exclusions_df):
    merged_df = pd.merge(student_df, exclusions_df, on="Email")
    merged_df[WORKSHOP_SESSION_HEADERS] = merged_df.apply(
        lambda row: erase_student_prefs(row)
    )
    merged_df = merged_df.drop(['Excluded Workshop'])
    return merged_df


def erase_student_prefs(row):
    for session in WORKSHOP_SESSION_HEADERS:
        if row[session] == row["Excluded Workshop"]:
            row[session] = "None"
    return row


def import_exclusions(exclusions_filepath):
    return pd.read_csv(exclusions_filepath, sep='\t')


# returns df with students placed in leftover workshops
# iterate over the student_df, for each with "Unscheduled",
# place them in a leftover workshop
def schedule_leftover_students(student_df, workshop_df):
    for session in WORKSHOP_SESSION_HEADERS:
        student_df[session] = (student_df[session].apply(
            lambda row: schedule_student_in_lowest_attended_freetalk(
                row, workshop_df, session)))
    return student_df


def schedule_student_in_lowest_attended_freetalk(row, workshop_df, session):
    # ensure student isn't already scheduled for the workshop by removing any rows for
    # that session from workshop_df where the student is already scheduled for that talk
    workshop_df_not_already_scheduled = workshop_df[workshop_df[session] != row[session]]

    lowest_attended_workshop = workshop_df_not_already_scheduled[

        workshop_df_not_already_scheduled["Is Freetalk"] == True &
        workshop_df_not_already_scheduled[f"Attendance Count Session {session}"]
        == workshop_df_not_already_scheduled[f"Attendance Count Session {session}"].min()]
    row[session] = lowest_attended_workshop["Name"]
    return row


def main():
    workshop_df = import_workshop_df('./data/workshop_data.tsv')
    student_df = import_student_preferences('./data/student_preferences.tsv')
    exclusions_df = import_exclusions('./data/exclusions.tsv')
    student_df = convert_workshop_pref_columns(student_df, workshop_df)
    student_df = schedule_eighth_grade_discussion(student_df, GRADE_8_WORKSHOP)
    student_df = erase_ineligible_student_prefs(student_df, exclusions_df)
    student_placements, workshop_enrollments = schedule_students(student_df, workshop_df)
    student_placements = schedule_leftover_students(student_placements, workshop_df)


if __name__ == '__main__':
    main()