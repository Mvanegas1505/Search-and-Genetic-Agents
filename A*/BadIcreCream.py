import pygame
import random
import heapq

# --- Configuración ---
WIDTH, HEIGHT = 600, 600
ROWS, COLS = 20, 20
CELL_SIZE = WIDTH // COLS
ICE_COST = 2   # Reducido: romper hielo es más atractivo

# --- Inicializar Pygame ---
pygame.init()
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Snake Auto A*")

# --- Colores ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
BLUE = (100, 100, 255)

# --- A* Pathfinding ---
def heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def astar(start, goal, grid):
    open_set = []
    heapq.heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            return path[::-1], g_score[goal]

        neighbors = [(0,1),(0,-1),(1,0),(-1,0)]
        for dx, dy in neighbors:
            neighbor = (current[0] + dx, current[1] + dy)
            if 0 <= neighbor[0] < ROWS and 0 <= neighbor[1] < COLS:
                step_cost = ICE_COST if grid[neighbor[1]][neighbor[0]] == 1 else 1
                tentative_g = g_score[current] + step_cost
                if tentative_g < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score, neighbor))

    return None, float('inf')

# --- Generar hielos ---
def generar_hielos(grid):
    # Hielos sueltos
    for _ in range(100):
        x, y = random.randint(0, COLS-1), random.randint(0, ROWS-1)
        grid[y][x] = 1

    # Bloques de hielo (zonas encerradas)
    for _ in range(5):  # 5 bloques de hielo grandes
        bx, by = random.randint(0, COLS-4), random.randint(0, ROWS-4)
        for i in range(3):
            for j in range(3):
                grid[by+j][bx+i] = 1

# --- Generar fruta en celda libre ---
def generar_fruta(grid):
    while True:
        x, y = random.randint(0, COLS-1), random.randint(0, ROWS-1)
        if grid[y][x] == 0:  # Solo en celdas libres
            return (x, y)

# --- Juego ---
def main():
    clock = pygame.time.Clock()

    # Preguntar al usuario cuántas frutas debe recoger
    frutas_objetivo = int(input("¿Cuántas frutas quieres que recoja el jugador? "))
    frutas_recogidas = 0

    # Crear mapa
    grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    generar_hielos(grid)

    # Jugador y fruta
    snake = [(5, 5)]
    fruit = generar_fruta(grid)

    path, tiempo_total = astar(snake[0], fruit, grid)
    path = path or []
    move_index = 0

    run = True
    while run:
        clock.tick(8)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                run = False

        if move_index < len(path):
            new_head = path[move_index]
            move_index += 1
            snake[0] = new_head

            # Si pisa hielo, romperlo (volverlo espacio normal)
            if grid[new_head[1]][new_head[0]] == 1:
                grid[new_head[1]][new_head[0]] = 0

            # Imprimir dirección en consola
            if move_index > 0:
                prev = path[move_index-1] if move_index-1 >= 0 else snake[0]
                dx, dy = new_head[0] - prev[0], new_head[1] - prev[1]
                if dx == 1: print("RIGHT")
                elif dx == -1: print("LEFT")
                elif dy == 1: print("DOWN")
                elif dy == -1: print("UP")

            # Comer fruta
            if snake[0] == fruit:
                frutas_recogidas += 1
                print(f"\n✅ Fruta {frutas_recogidas} recogida en {tiempo_total} de tiempo total\n")

                if frutas_recogidas >= frutas_objetivo:
                    print("🎉 ¡Se recogieron todas las frutas!")
                    break

                # Generar nueva fruta en celda libre
                fruit = generar_fruta(grid)
                path, tiempo_total = astar(snake[0], fruit, grid)
                path = path or []
                move_index = 0

        # --- Dibujar ---
        WIN.fill(BLACK)
        for y in range(ROWS):
            for x in range(COLS):
                if grid[y][x] == 1:
                    pygame.draw.rect(WIN, BLUE, (x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE))
        pygame.draw.rect(WIN, RED, (fruit[0]*CELL_SIZE, fruit[1]*CELL_SIZE, CELL_SIZE, CELL_SIZE))
        pygame.draw.rect(WIN, GREEN, (snake[0][0]*CELL_SIZE, snake[0][1]*CELL_SIZE, CELL_SIZE, CELL_SIZE))
        pygame.display.update()

    pygame.quit()

if _name_ == "_main_":
    main()
