class_name CarSoccer
extends RefCounted
## Car soccer on the stadium: blue (left goal) against red (right goal).
## The ball has its own simple physics: it rolls, slows down, bounces off
## the walls and off the cars (a moving car kicks it, a boosting car hard).
## 3:00 or first to 5 goals.

const TIME := 180.0
const GOALS_TO_WIN := 5
const BALL_R := 8.0
const CAR_R := 9.0
const GOAL_POINTS := 1500

var race: RaceManager
var teams: Array = [[], []]      # 0 blue attacks right, 1 red attacks left
var score := [0, 0]
var goals: Dictionary = {}       # car -> goals scored
var ball := Vector2.ZERO
var ball_v := Vector2.ZERO
var last_touch: Car
var _pause := 0.0                # after a goal
var _spin := 0.0


func setup(the_race: RaceManager, blue: Array, red: Array) -> void:
	race = the_race
	teams = [blue, red]
	for t in 2:
		for c in teams[t]:
			goals[c] = 0
			(c as Car).badge = "BLUE" if t == 0 else "RED"
			(c as Car).badge_color = Color("6aa0ff") if t == 0 else Color("ff6a6a")
	kickoff()


func team_of(c: Car) -> int:
	return 0 if c in teams[0] else 1


func kickoff() -> void:
	var r := race.track_data.arena_rect
	var c := r.get_center()
	ball = c
	ball_v = Vector2.ZERO
	for t in 2:
		var side := -1.0 if t == 0 else 1.0
		var n: int = (teams[t] as Array).size()
		for k in n:
			var car := teams[t][k] as Car
			var y := c.y + (k - (n - 1) * 0.5) * 70.0
			car.place(Vector2(c.x + side * (160.0 + (k % 2) * 90.0), y), 0.0 if t == 0 else PI)
			car.velocity = Vector2.ZERO


func tick(dt: float) -> void:
	_steer_bots()
	if _pause > 0.0:
		_pause -= dt
		if _pause <= 0.0:
			kickoff()
		return
	var r := race.track_data.arena_rect
	var cy := r.get_center().y
	var gh := race.track_data.goal_h * 0.5
	ball_v *= exp(-0.55 * dt)
	ball += ball_v * dt
	_spin += ball_v.length() * dt * 0.15
	# Cars kick the ball.
	for t in 2:
		for c in teams[t]:
			var car := c as Car
			var d := ball - car.global_position
			var dist := d.length()
			if dist < BALL_R + CAR_R and dist > 0.01:
				var n := d / dist
				ball = car.global_position + n * (BALL_R + CAR_R)
				var rel := ball_v - car.velocity
				var along := rel.dot(n)
				if along < 0.0:
					var kick := 1.25 if car.boost_t > 0.0 else 1.0
					ball_v = car.velocity * kick + (rel - n * along * 1.7)
					ball_v += n * 40.0
					last_touch = car
					if absf(along) > 150.0:
						AudioManager.play("bump", 1.3, -8.0)
	# Walls; the goal mouths are open.
	var in_mouth := absf(ball.y - cy) < gh - BALL_R
	if ball.y < r.position.y + BALL_R:
		ball.y = r.position.y + BALL_R
		ball_v.y = absf(ball_v.y) * 0.8
	elif ball.y > r.end.y - BALL_R:
		ball.y = r.end.y - BALL_R
		ball_v.y = -absf(ball_v.y) * 0.8
	if not in_mouth:
		if ball.x < r.position.x + BALL_R:
			ball.x = r.position.x + BALL_R
			ball_v.x = absf(ball_v.x) * 0.8
		elif ball.x > r.end.x - BALL_R:
			ball.x = r.end.x - BALL_R
			ball_v.x = -absf(ball_v.x) * 0.8
	elif ball.x < r.position.x - BALL_R:
		_goal(1)
	elif ball.x > r.end.x + BALL_R:
		_goal(0)


func _goal(team: int) -> void:
	score[team] += 1
	var who := last_touch
	var text := Lang.t("GOAL! BLUE") if team == 0 else Lang.t("GOAL! RED")
	if who and team_of(who) == team:
		goals[who] = int(goals[who]) + 1
		who.scoring.total += GOAL_POINTS
		who.scoring.popup.emit(Lang.t("GOAL!"), GOAL_POINTS, "zone")
		text += " — " + race.short_name(who)
	elif who:
		text += " — " + Lang.t("own goal by %s") % race.short_name(who)
	race.views.message_all(text, Color("6aa0ff") if team == 0 else Color("ff6a6a"), 2.2)
	AudioManager.play("reward", 1.0, 0.0)
	for cam in race.views.cameras:
		(cam as CameraController).shake(5.0)
	ball_v *= 0.2
	_pause = 2.2


## Attackers go round behind the ball and push it at the other goal; the
## last bot of a team with three or more stays back as the keeper.
func _steer_bots() -> void:
	var r := race.track_data.arena_rect
	var cy := r.get_center().y
	for t in 2:
		var target := Vector2(r.end.x + 20.0, cy) if t == 0 else Vector2(r.position.x - 20.0, cy)
		var own := Vector2(r.position.x + 30.0, cy) if t == 0 else Vector2(r.end.x - 30.0, cy)
		var members: Array = teams[t]
		for k in members.size():
			var car := members[k] as Car
			var drv := car.controller as FieldDriver
			if drv == null:
				continue
			drv.want_speed = 9999.0
			if members.size() >= 3 and k == members.size() - 1:
				# Keeper: between the ball and the own goal.
				drv.aim = own.lerp(ball, 0.25)
				continue
			var to_goal := (target - ball).normalized()
			var behind := ball - to_goal * 26.0
			var p := car.global_position
			var lined_up := (ball - p).normalized().dot(to_goal) > 0.6 and p.distance_to(ball) < 140.0
			if lined_up:
				drv.aim = ball + to_goal * 20.0 + ball_v * 0.15
			else:
				# Drive round the ball, not through it the wrong way.
				var side := Vector2(-to_goal.y, to_goal.x)
				if (p - ball).dot(side) < 0.0:
					side = -side
				drv.aim = behind + side * 30.0 if (p - ball).dot(to_goal) > -10.0 else behind
				drv.aim = drv.aim.clamp(r.position + Vector2(12, 12), r.end - Vector2(12, 12))


func is_done() -> bool:
	return race.race_time >= TIME or score[0] >= GOALS_TO_WIN or score[1] >= GOALS_TO_WIN


func mode_line(car: Car) -> String:
	var t := RaceHUD.format_time(maxf(TIME - race.race_time, 0.0)).substr(0, 5)
	var mine := Lang.t("YOU: BLUE →") if team_of(car) == 0 else Lang.t("YOU: ← RED")
	return Lang.t("BLUE %d : %d RED   %s   %s") % [score[0], score[1], t, mine]


func title() -> String:
	if score[0] == score[1]:
		return Lang.t("DRAW %d : %d") % [score[0], score[1]]
	return (Lang.t("BLUE WINS %d : %d") if score[0] > score[1] else Lang.t("RED WINS %d : %d")) % [score[0], score[1]]


func cell(c: Car) -> String:
	return (Lang.t("BLUE") if team_of(c) == 0 else Lang.t("RED")) + " · " + Lang.t("%d goals") % int(goals.get(c, 0))


func draw_world(ci: CanvasItem) -> void:
	ci.draw_circle(ball + Vector2(2, 3), BALL_R, Color(0, 0, 0, 0.35))
	ci.draw_circle(ball, BALL_R, Color("f4f4f4"))
	# Spinning black patches.
	for k in 3:
		var a := _spin + TAU * k / 3.0
		ci.draw_circle(ball + Vector2.from_angle(a) * 4.0, 2.2, Color("1c1c22"))
	ci.draw_arc(ball, BALL_R, 0, TAU, 20, Color("1c1c22"), 1.0)
	for c in race.humans:
		var car := c as Car
		if car.global_position.distance_to(ball) > 120.0:
			Delivery._arrow(ci, car, ball, Color.WHITE)
