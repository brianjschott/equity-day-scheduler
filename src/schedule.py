import pandas as pd
import matplotlib.pyplot as plt
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


GRADE_8_WORKSHOP_SESSION = 1
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
    student_placements[WORKSHOP_SESSION_HEADERS] = "Unscheduled"
    workshop_enrollments = workshop_df[['Name', 'Location', 'Max Attendance', 'FreeTalk Status', 'Availability', '8th graders']]

    student_placements = schedule_workshop_facilitators(student_placements, import_student_facilitator_df('./data/facilitators.tsv'), workshop_df)
    student_preference_df = (
        erase_ineligible_student_prefs(student_preference_df, import_exclusions('./data/exclusions.tsv')))
    student_preference_df.loc[student_preference_df['Grade'] == 8, f'Session {GRADE_8_WORKSHOP_SESSION}'] = "8th Grade Discussion"
    for i in range(1, WORKSHOP_NUM_SESSIONS + 1):
        workshop_enrollments.loc[:, f'Attendance Count Session {i}'] = 0
    student_placements, workshop_enrollments = schedule_eighth_grade_discussion(student_placements, workshop_enrollments)
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
                                on='Email', how='left', suffixes=('_x', ''))
                data = data.loc[:, ~data.columns.str.endswith('_x')]  # drops repeat cols on merge
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
                    student_placements.loc[
                        student_placements['Email'].isin(students_selected["Email"]), f"Session {session}"] = workshop
                    student_placements.loc[
                        student_placements['Email'].isin(students_selected["Email"]), f"Session {session} Location"] = workshop_df.loc[workshop_df['Name'] == workshop, 'Location'].values[0]
                    workshop_enrollments.loc[
                        workshop_enrollments['Name'] == workshop, f'Attendance Count Session {session}'] += len(
                        students_selected)
    return student_placements, workshop_enrollments


# anyone who is an 8th grader gets a discussion section at that period
def schedule_eighth_grade_discussion(student_df, workshop_enrollments):

    # for each student, schedule them in the lowest attended 8th grade workshop
    student_df = student_df.apply(lambda row: schedule_eighth_grader(row, workshop_enrollments), axis=1)

    return student_df, workshop_enrollments


def schedule_eighth_grader(row, workshop_enrollments):
    #only schedule eighth graders
    if row['Grade'] != 8:
        return row
    # schedule lowest_attended_workshop: has to be...
    # 1) a session 1
    # 2) have empty slots
    # 3) be the lowest attended workshop in the list of eighth grader sessions
    eighth_grade_workshops = workshop_enrollments[workshop_enrollments['8th graders'] == True]
    # get all 8th grade discussion section cols
    eighth_grade_workshops_are_available = eighth_grade_workshops[eighth_grade_workshops[f"Attendance Count Session {GRADE_8_WORKSHOP_SESSION}"]
        < eighth_grade_workshops['Max Attendance']]

    lowest_attendance_eighth_grade_workshop = eighth_grade_workshops_are_available[
        eighth_grade_workshops_are_available[f"Attendance Count Session {GRADE_8_WORKSHOP_SESSION}"]
        == eighth_grade_workshops_are_available[f"Attendance Count Session {GRADE_8_WORKSHOP_SESSION}"].min()].iloc[0]

    # add that workshop's name to the student
    row[f"Session {GRADE_8_WORKSHOP_SESSION}"] = lowest_attendance_eighth_grade_workshop["Name"]
    row[f"Session {GRADE_8_WORKSHOP_SESSION} Location"] = lowest_attendance_eighth_grade_workshop["Location"]
    workshop_enrollments.loc[
        workshop_enrollments['Name'] == lowest_attendance_eighth_grade_workshop['Name'], f'Attendance Count Session {GRADE_8_WORKSHOP_SESSION}'] += 1
    return row

# schedules workshop moderators into their designated sessions
# spreadsheet lists name, email, workshop, and sessions
# returns student df, workshop_df not necessary because these students don't
# count for attendance purposes
def schedule_workshop_facilitators(student_placements, student_facilitators_df, workshop_df):
    student_facilitators_df.apply(lambda row: add_facilitator_to_workshop(row, student_placements, workshop_df), axis=1)
    return student_placements


def add_facilitator_to_workshop(row, student_df, workshop_df):
    # get availability from row, convert to array
    session_list = [s.strip() for s in row['Sessions'].split(',')]
    workshop_name = row["Name"]
    for session in session_list:
        student_df.loc[student_df['Email'] == row['Email'], f'Session {session}'] = workshop_name
        student_df.loc[student_df['Email'] == row['Email'], f'Session {session} Location'] = workshop_df.loc[workshop_df['Name'] == workshop_name, 'Location'].values[0]

    return row


# takes student_df and exclusions_df
# changes all instances of workshop preferences
def erase_ineligible_student_prefs(student_df, exclusions_df):
    merged_df = pd.merge(student_df, exclusions_df, on="Email", how="outer")
    merged_df = merged_df.apply(
        lambda row: erase_student_prefs(row), axis=1
    )
    merged_df = merged_df.drop(['Excluded Workshop'], axis=1)
    return merged_df


def erase_student_prefs(row):
    for pref in NUMBER_OF_PREFERENCES_LIST:
        if row[f'Preference {pref}'] == row["Excluded Workshop"]:
            row[f'Preference {pref}'] = "None"
    return row


def import_exclusions(exclusions_filepath):
    return pd.read_csv(exclusions_filepath, sep='\t', header=0)


# returns df with students placed in leftover workshops
# iterate over the student_df, for each with "Unscheduled",
# place them in a leftover workshop
def schedule_leftover_students(student_df, workshop_df, workshop_enrollments):

    for session in range(1, WORKSHOP_NUM_SESSIONS + 1):
        #print("Leftovers for session " + str(session))
        #print(student_df[student_df[f"Session {session}"] == "Unscheduled"])
        student_df = student_df.apply(
            lambda row: schedule_student_in_lowest_attended_freetalk(
                row, workshop_df, session, workshop_enrollments), axis=1)
        #print("Now the leftovers are...")
        #print(student_df[student_df[f"Session {session}"] == "Unscheduled"])

    return student_df, workshop_enrollments


def schedule_student_in_lowest_attended_freetalk(row, workshop_df, session, workshop_enrollments):
    # ensure student isn't already scheduled for the workshop by removing any rows for
    # that session from workshop_df where the student is already scheduled for that talk
    workshop_df_not_already_scheduled = workshop_enrollments[~workshop_enrollments['Name'].isin(row[WORKSHOP_SESSION_HEADERS])]

    #if no workshops meet this criteria, return the row with nothing changed
    if workshop_df_not_already_scheduled.shape[0] < 1 or row[f'Session {session}'] != 'Unscheduled':
        return row

    # schedule lowest_attended_workshop: has to be...
    # 1) a freetalk
    # 2) have empty slots
    # 3) be the lowest attended workshop in the list of free talks

    free_talks_eligible = workshop_df_not_already_scheduled[workshop_df_not_already_scheduled.apply(
        lambda r: True if r["FreeTalk Status"] == "Open"
        and r[f"Attendance Count Session {session}"] < r['Max Attendance']
        and (str(session)) in r['Availability'] else False, axis=1)]

    lowest_attended_workshop = free_talks_eligible[free_talks_eligible.apply(
        lambda r: True if r[f"Attendance Count Session {session}"] == free_talks_eligible[f"Attendance Count Session {session}"].min()
        else False, axis=1)].iloc[0]

    #add that workshop's name to the student
    row[f'Session {session}'] = lowest_attended_workshop["Name"]
    row[f'Session {session} Location'] = lowest_attended_workshop["Location"]
    workshop_enrollments.loc[
        workshop_enrollments['Name'] == lowest_attended_workshop["Name"], f'Attendance Count Session {session}'] += 1
    return row


def main():
    workshop_df = import_workshop_df('./data/workshop_data.tsv')
    student_df = import_student_preferences('./data/student_preferences.tsv')
    student_df = convert_workshop_pref_columns(student_df, workshop_df)

    all_emails_df = pd.read_csv('./data/all_emails.tsv', sep='\t')
    all_emails_df = all_emails_df.rename(columns={'Full Name': 'Name'})


    student_df = pd.merge(left=student_df, right=all_emails_df, how='outer', on=['Email', 'Grade'])
    student_df = student_df.drop_duplicates(subset=['Email'], keep='first', ignore_index=True)
    student_df['Name_x'] = student_df['Name_x'].fillna(student_df['Name_y'])
    student_df = student_df.rename(columns={'Name_x': 'Name'})
    student_df = student_df.drop(columns=['Name_y'])

    student_placements, workshop_enrollments = schedule_students(student_df, workshop_df)

    student_placements, workshop_enrollments = schedule_leftover_students(student_placements, workshop_df, workshop_enrollments)

    student_placements.to_csv('./data/student_placements.tsv', sep='\t')

    for session in range(1, WORKSHOP_NUM_SESSIONS + 1):
        workshop_enrollments = workshop_enrollments.apply(lambda row:get_students_for_workshop(row, student_placements, session), axis=1)
    workshop_enrollments.to_csv('./data/workshop_enrollments.tsv', sep='\t')

    check_for_dupes(student_placements)
    get_stats(workshop_enrollments)

def get_stats(workshop_enrollments):
    # show attendance for each workshop as a histogram in groups
    for session in range(1, WORKSHOP_NUM_SESSIONS + 1):
        session_attendance_count = workshop_enrollments[['Name', f'Attendance Count Session {session}']]
        fig, ax = plt.subplots()
        plt.figure(figsize=(20,3))
        plt.xticks(rotation=45)
        ax.bar(workshop_enrollments['Name'], workshop_enrollments[f'Attendance Count Session {session}'])
        ax.set_xlabel('Workshops')
        ax.set_ylabel('Attendance Count')
        ax.set_title(f'Session {session}')

        plt.show()
        plt.savefig(f'./data/attendance_session{session}.png', bbox_inches='tight')

def check_for_dupes(student_placements):
    # get rows that have values repeated
    student_placement_duplicates = student_placements[student_placements[WORKSHOP_SESSION_HEADERS].apply(lambda row: has_duplicates(row), axis=1)]
    facilitators = import_student_facilitator_df('./data/facilitators.tsv')
    student_placement_duplicates_not_facilitators = student_placement_duplicates[~student_placement_duplicates['Email'].isin(facilitators['Email'])]
    if (len(student_placement_duplicates_not_facilitators) > 0):
        print('Duplicates are: ')
        print(student_placement_duplicates_not_facilitators)
    else:
        print('No duplicates')


def has_duplicates(row):
    # convert row to list
    # loop over list, if the element is repeated, return True
    # else return False
    row = row.array
    for i in range(len(row)):
        for j in range(i+1, len(row)):
            if row[i] == row[j]:
                return True
    return False

def get_students_for_workshop(row, student_placements, session):
    workshop_name = row['Name']
    row[f'Session {session} Roster Names'] = student_placements.loc[
        student_placements[f'Session {session}'] == workshop_name, 'Name'].values
    row[f'Session {session} Roster Names'] = ",".join(str(x) for x in row[f'Session {session} Roster Names'])
    row[f'Session {session} Roster Emails'] = student_placements.loc[
        student_placements[f'Session {session}'] == workshop_name, 'Email'].values
    row[f'Session {session} Roster Emails'] = ",".join(str(x) for x in row[f'Session {session} Roster Emails'])
    return row


if __name__ == '__main__':
    main()