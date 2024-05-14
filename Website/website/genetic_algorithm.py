import random
import mysql.connector
import openpyxl

# Create a MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="1234",
    database="university_timetable"
)

def genetic_algorithm(year_levels, programs, student_groups, population_size = 550, generations = 100, mutation_rate = 0.01):
    # Step 1: Initialize the population
    population = []
    best_fitness_scores = []
    avg_fitness_scores = []
    thresholds = []

    for _ in range(population_size):
        timetable = generate_timetable(year_levels, programs, student_groups)
        population.append(timetable)
    
    # Step 2: Evolutionary loop
    for generation in range(generations):
        print(f"Generation {generation + 1}")

        # Step 2a: Evaluate fitness
        fitness_scores = evaluate_fitness(population)
        print(f"Fitness scores: {fitness_scores}")

        # Check if the maximum fitness score reaches 1.0
        if 1.0 in fitness_scores:
            print("Terminating early as fitness score reached 1.0.")
            break

        # Step 2b: Select parents for reproduction
        parents = selection(population)
        #print(f"Selected parents: {parents}")

        # Step 2c: Apply genetic operators (crossover and mutation) to create offspring
        offspring = crossover(parents)
        offspring = mutation(offspring, mutation_rate)
        #print(f"Offspring: {offspring}")

        # Step 2d: Evaluate fitness of offspring
        offspring_fitness_scores = evaluate_fitness(offspring)
        #print(f"Offspring fitness scores: {offspring_fitness_scores}")

        # Step 2e: Select survivors for the next generation
        population = survival_selection(population, fitness_scores, offspring, offspring_fitness_scores, num_individuals = 550)
        #print(f"Survivors: {population}")
        #print("----------------------------------------------------------------------------------------------------------------------------")

        # Calculate best fitness, average fitness, and threshold for the current generation
        best_fitness = max(fitness_scores)
        avg_fitness = sum(fitness_scores) / len(fitness_scores)
        threshold = best_fitness + (avg_fitness - best_fitness) * 0.2  # Adjust the threshold calculation as needed

        best_fitness_scores.append(best_fitness)
        avg_fitness_scores.append(avg_fitness)
        thresholds.append(threshold)

        # Check termination condition
        if generation == generations - 1:
            break

    # Step 3: Return the best solution
    fitness_scores = evaluate_fitness(population)
    best_fitness_score = max(fitness_scores)
    print(best_fitness_score)
    best_timetable = get_best_timetable(population, fitness_scores)

    # Write data to Excel file
    write_to_excel(best_fitness_scores, avg_fitness_scores, thresholds)

    return best_timetable

def generate_timetable(year_levels, programs, student_groups):
    cursor = db.cursor()

    # Convert year_levels, programs, and student_groups into a string format for the query
    year_levels_str = ", ".join(map(str, year_levels))
    programs_str = ", ".join(map(lambda x: f"'{x}'", programs))
    student_groups_str = ", ".join(map(lambda x: f"'{x}'", student_groups))

    query = (
        "SELECT classgroup.gid, classgroup.class_type, classgroup.cid, course.course_name, classgroup.duration, "
        "studentgroup.year_level, studentgroup.program, studentgroup.studentgroup_name "
        "FROM classgroup "
        "INNER JOIN studentgroup ON classgroup.gid = studentgroup.gid "
        "INNER JOIN course ON classgroup.cid = course.cid "
        f"WHERE studentgroup.year_level IN ({year_levels_str}) "
        f"AND studentgroup.program IN ({programs_str}) "
        f"AND studentgroup.studentgroup_name IN ({student_groups_str})"
    )

    cursor.execute(query)
    classgroups = cursor.fetchall()
    cursor.nextset()  # Clear the unread result

    if not classgroups:
        return []

    cursor.execute("SELECT rid, seat, room_type FROM room")
    rooms = cursor.fetchall()
    cursor.nextset()  # Clear the unread result

    timetable = []

    assigned_lecturers = {}  # Dictionary to store lecturer assignments

    for classgroup in classgroups:
        gid, class_type, cid, course_name, duration, year_level, program, student_group = classgroup

        assigned = False
        while not assigned:
            day = random.choice(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
            hour = random.randint(9, 16)  # Adjusted to allow for consecutive hours

            room_id = random.choice(rooms)[0]

            # Calculate a unique identifier for the class group based on specified attributes
            class_group_identifier = (cid, course_name, year_level, program, student_group)

            # Check if this combination has already been assigned a lecturer
            if class_group_identifier in assigned_lecturers:
                lecturer_name = assigned_lecturers[class_group_identifier]
            else:
                # If not, assign a lecturer
                lecturer_name = get_preferred_lecturer(cid)

                # Store the assigned lecturer in the dictionary
                assigned_lecturers[class_group_identifier] = lecturer_name

            # Check if there's room for a consecutive hour
            if duration > 1:  # Check if there's room for consecutive hour
                consecutive_hour = hour + 1
            else:
                consecutive_hour = None

            timeslot = {
                "day": day,
                "hour": hour,
                "consecutive_hour": consecutive_hour,
                "gid": gid,
                "class_type": class_type,
                "cid": cid,
                "duration": duration,
                "course_name": course_name,
                "room_id": room_id,
                "lecturer_name": lecturer_name,
                "year_level": year_level,
                "program": program,
                "student_group": student_group
            }

            timetable.append(timeslot)
            assigned = True

    return timetable

def evaluate_fitness(population):
    fitness_scores = []
    
    for timetable in population:
        violated_hard_constraints = 0
        fulfilled_soft_constraints = 0
        total_hard_constraints = 0  
        total_soft_constraints = 0

        # Hard constraint 1: A room should not be assigned on the same day and same hour
        assigned_rooms_per_timeslot = {}  # Track assigned rooms for each day and hour
        for timeslot in timetable:
            day = timeslot["day"]
            hour = timeslot["hour"]
            room_id = timeslot["room_id"]

            if (day, hour) in assigned_rooms_per_timeslot:
                if room_id in assigned_rooms_per_timeslot[(day, hour)]:
                    violated_hard_constraints += 1
                else:
                    assigned_rooms_per_timeslot[(day, hour)].add(room_id)
            else:
                assigned_rooms_per_timeslot[(day, hour)] = {room_id}

            if timeslot["consecutive_hour"] is not None:
                consecutive_room_id = timeslot["room_id"]
                if (day, timeslot["consecutive_hour"]) in assigned_rooms_per_timeslot:
                    if consecutive_room_id in assigned_rooms_per_timeslot[(day, timeslot["consecutive_hour"])]:
                        violated_hard_constraints += 1
                    else:
                        assigned_rooms_per_timeslot[(day, timeslot["consecutive_hour"])].add(consecutive_room_id)
                else:
                    assigned_rooms_per_timeslot[(day, timeslot["consecutive_hour"])] = {consecutive_room_id}

            total_hard_constraints += 1

        # Hard Constraint 2: Class should not be assigned on 13:00 - 14:00
        for timeslot in timetable:
            start_time = timeslot["hour"]
            if 12 <= start_time < 13 or 13 <= start_time < 14:
                violated_hard_constraints += 1
        total_hard_constraints += 1

        # Hard Constraint 3: Students and lecturers must not be assigned on the same day and hour
        assigned_groups_and_lecturers_per_timeslot = {}  # Track assigned groups and lecturers for each day and hour
        for timeslot in timetable:
            day = timeslot["day"]
            hour = timeslot["hour"]
            year_level = timeslot["year_level"]
            program = timeslot["program"]
            student_group = timeslot["student_group"]
            lecturer_name = timeslot["lecturer_name"]

            key = (day, hour)
            if key in assigned_groups_and_lecturers_per_timeslot:
                if (year_level, program, student_group) in assigned_groups_and_lecturers_per_timeslot[key][0]:
                    violated_hard_constraints += 1
                if lecturer_name in assigned_groups_and_lecturers_per_timeslot[key][1]:
                    violated_hard_constraints += 1
            else:
                assigned_groups_and_lecturers_per_timeslot[key] = (set(), set())
            assigned_groups_and_lecturers_per_timeslot[key][0].add((year_level, program, student_group))
            assigned_groups_and_lecturers_per_timeslot[key][1].add(lecturer_name)

            if timeslot["consecutive_hour"] is not None:
                consecutive_key = (day, timeslot["consecutive_hour"])
                if consecutive_key in assigned_groups_and_lecturers_per_timeslot:
                    if (year_level, program, student_group) in assigned_groups_and_lecturers_per_timeslot[consecutive_key][0]:
                        violated_hard_constraints += 1
                    if lecturer_name in assigned_groups_and_lecturers_per_timeslot[consecutive_key][1]:
                        violated_hard_constraints += 1
                else:
                    assigned_groups_and_lecturers_per_timeslot[consecutive_key] = (set(), set())
                assigned_groups_and_lecturers_per_timeslot[consecutive_key][0].add((year_level, program, student_group))
                assigned_groups_and_lecturers_per_timeslot[consecutive_key][1].add(lecturer_name)

            total_hard_constraints += 2  # Count both group and lecturer constraints

        # Hard Constraint 4: Room id's room type must match class type
        for timeslot in timetable:
            room_id = timeslot["room_id"]
            class_type = timeslot["class_type"]
            room_type = get_room_type_for_room(room_id)
            if room_type != class_type:
                violated_hard_constraints += 1
            total_hard_constraints += 1

        # Hard Constraint 5: A class must be assigned by a qualified lecturer
        for timeslot in timetable:
            lecturer_name = timeslot["lecturer_name"]
            class_group_id = timeslot["gid"]  # Use the class group ID instead of course_id
            qualified_lecturers = get_qualified_lecturers_for_group(class_group_id)
            if lecturer_name not in qualified_lecturers:
                violated_hard_constraints += 1
            total_hard_constraints += 1

        # Soft Constraint: A class can be assigned by a preference lecturer
        for timeslot in timetable:
            lecturer_name = timeslot["lecturer_name"]
            class_group_id = timeslot["gid"]
            qualified_lecturers = get_preferred_lecturers_for_group(class_group_id)  # Use the function for preferred lecturers
            if lecturer_name in qualified_lecturers:
                fulfilled_soft_constraints += 1
            total_soft_constraints += 1

        fitness = (1 - (violated_hard_constraints / total_hard_constraints)) * 0.85 + (fulfilled_soft_constraints / total_soft_constraints) * 0.15
        fitness_scores.append(fitness)

    return fitness_scores

def selection(population):
    tournament_size = 2
    selected_parents = []

    for _ in range(len(population)):
        # Select two random individuals from the population for the tournament
        tournament = random.choices(population, k=tournament_size)

        # Remove any timetables with empty classgroups from the tournament
        tournament = [individual for individual in tournament if any(individual)]

        # Check if any individuals are left in the tournament
        if tournament:
            # Calculate fitness scores for the individuals in the tournament
            tournament_fitness = evaluate_fitness(tournament)

            # Select the individual with the highest fitness score as the winner of the tournament
            winner = tournament[tournament_fitness.index(max(tournament_fitness))]
            selected_parents.append(winner)

    return selected_parents

def crossover(parents):
    offspring = []

    for i in range(0, len(parents), 2):
        if i + 1 < len(parents):
            parent1 = parents[i]
            parent2 = parents[i + 1]

            offspring1, offspring2 = uniform_crossover(parent1, parent2)

            offspring.append(offspring1)
            offspring.append(offspring2)

    return offspring

def uniform_crossover(parent1, parent2):
    mask = [random.choice([0, 1]) for _ in range(len(parent1))]

    offspring1 = [parent1[i] if mask[i] == 0 else parent2[i] for i in range(len(parent1))]
    offspring2 = [parent2[i] if mask[i] == 0 else parent1[i] for i in range(len(parent1))]

    return offspring1, offspring2

def mutation(offspring, mutation_rate):
    mutated_offspring = []

    for individual in offspring:
        if random.random() < mutation_rate:
            # Choose two distinct random indices to swap
            index1, index2 = random.sample(range(len(individual)), 2)

            # Perform the swap mutation
            mutated_individual = individual.copy()
            mutated_individual[index1], mutated_individual[index2] = mutated_individual[index2], mutated_individual[index1]

            mutated_offspring.append(mutated_individual)
        else:
            mutated_offspring.append(individual)

    return mutated_offspring

def survival_selection(population, fitness_scores, offspring, offspring_fitness_scores, num_individuals):
    combined_population = population + offspring
    combined_fitness_scores = fitness_scores + offspring_fitness_scores
    next_generation = []

    for _ in range(num_individuals):
        max_fitness_index = combined_fitness_scores.index(max(combined_fitness_scores))
        next_generation.append(combined_population[max_fitness_index])

        # Remove the selected individual from the combined population and fitness scores
        del combined_population[max_fitness_index]
        del combined_fitness_scores[max_fitness_index]

    return next_generation

def write_to_excel(best_fitness_scores, avg_fitness_scores, thresholds):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Fitness Data"

    sheet["A1"] = "Generation"
    sheet["B1"] = "Best Fitness"
    sheet["C1"] = "Average Fitness"
    sheet["D1"] = "Threshold"

    for row_idx, (best, avg, threshold) in enumerate(zip(best_fitness_scores, avg_fitness_scores, thresholds), start=2):
        sheet[f"A{row_idx}"] = row_idx - 1  # Generation number
        sheet[f"B{row_idx}"] = best
        sheet[f"C{row_idx}"] = avg
        sheet[f"D{row_idx}"] = threshold

    excel_filename = "fitness_data.xlsx"
    workbook.save(excel_filename)
    print(f"Data saved to {excel_filename}")

def get_best_timetable(population, fitness_scores):
    best_index = fitness_scores.index(max(fitness_scores))
    best_timetable = population[best_index]
    return best_timetable

def get_qualified_lecturers_for_group(class_group_id):
    cursor = db.cursor()

    cursor.execute(
        "SELECT lecturer.lecturer_name "
        "FROM classgroup "
        "INNER JOIN lecturer_qualifications ON classgroup.cid = lecturer_qualifications.cid "
        "INNER JOIN lecturer ON lecturer_qualifications.lid = lecturer.lid "
        "WHERE classgroup.gid = %s",
        (class_group_id,)
    )
    lecturers = [row[0] for row in cursor.fetchall()]

    cursor.close()

    return lecturers

def get_preferred_lecturers_for_group(class_group_id):
    cursor = db.cursor()

    # Fetch lecturers from the database who prefer to teach the given class group
    cursor.execute(
        "SELECT lecturer.lecturer_name "
        "FROM classgroup "
        "INNER JOIN lecturer_preferences ON classgroup.cid = lecturer_preferences.cid "
        "INNER JOIN lecturer ON lecturer_preferences.lid = lecturer.lid "
        "WHERE classgroup.gid = %s",
        (class_group_id,)
    )
    lecturers = [row[0] for row in cursor.fetchall()]

    cursor.close()

    return lecturers

def get_preferred_lecturer(course_id):
    cursor = db.cursor()

    # Fetch lecturers from the database who prefer to teach the given course
    cursor.execute(
        "SELECT lecturer.lecturer_name "
        "FROM lecturer_preferences "
        "INNER JOIN lecturer ON lecturer_preferences.lid = lecturer.lid "
        "WHERE lecturer_preferences.cid = %s",
        (course_id,)
    )
    lecturers = [row[0] for row in cursor.fetchall()]

    cursor.close()

    if lecturers:
        return random.choice(lecturers)
    else:
        return get_qualified_lecturers_for_group(course_id)[0]  # If no preferred lecturer, select any qualified lecturer

def get_room_type_for_room(room_id):
    cursor = db.cursor()

    cursor.execute("SELECT room_type FROM room WHERE rid = %s", (room_id,))
    room_type = cursor.fetchone()[0]

    cursor.close()

    return room_type