import random
import threading
import time
import sqlite3
import traceback
from concurrent.futures import ThreadPoolExecutor
import collections
import math
import pygame

def init_database():
    conn = sqlite3.connect("World_simulator.db")
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS countries")
    cursor.execute("""
    CREATE TABLE countries (
        name TEXT,
        population INTEGER,
        happiness INTEGER,
        production INTEGER,
        year INTEGER,
        government TEXT,
        tech_level INTEGER,
        education_level INTEGER,
        military_power INTEGER,
        money INTEGER,
        pollution INTEGER,
        rebellion_risk REAL,
        oil INTEGER,
        coal INTEGER,
        gas INTEGER,
        forest INTEGER,
        invest_economy INTEGER,
        invest_environment INTEGER,
        invest_infrastructure INTEGER,
        infrastructure_level INTEGER,
        ideology_score INTEGER,
        environment_agreement INTEGER
    )
    """)
    conn.commit()
    conn.close()

print_lock = threading.Lock()
db_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs, flush=True)
        with open("simulation_log.txt", "a", encoding="utf-8") as f:
            print(*args, file=f)
            if 'exception' in kwargs:
                print(traceback.format_exc(), file=f)

class RLAgent:
    def __init__(self):
        self.alpha = 0.1
        self.gamma = 0.9
        self.epsilon = 0.3  # Start with higher exploration, can decay if needed
        self.invest_q = collections.defaultdict(lambda: {'economy': 0, 'environment': 0, 'infrastructure': 0})
        self.agree_q = collections.defaultdict(lambda: {'join': 0, 'refuse': 0})
        self.war_q = collections.defaultdict(lambda: {'attack': 0, 'peace': 0})

    def get_state(self, country, tension=None):
        hap = min(5, country.happiness // 20)
        pol = min(5, country.pollution // 20)
        infra = min(5, country.infrastructure_level // 20)
        prod = min(5, int(country.production) // 50)
        gov = 0 if country.government == 'right' else 1
        eco = min(5, world.ecosystem.ecosystem_health // 20)
        state = (hap, pol, infra, prod, gov, eco)
        if tension is not None:
            tens = min(5, max(0, (tension - 50) // 10))
            state += (tens,)
        return state

    def choose_action(self, q_table, state):
        if random.random() < self.epsilon:
            return random.choice(list(q_table[state].keys()))
        else:
            return max(q_table[state], key=q_table[state].get)

    def update(self, q_table, state, action, reward, new_state):
        max_next = max(q_table[new_state].values())
        q_table[state][action] += self.alpha * (reward + self.gamma * max_next - q_table[state][action])

class Ecosystem:
    def __init__(self, countries):
        self.countries = countries
        self.global_pollution = sum(c.pollution for c in countries) / len(countries)
        self.regional_pollution = {c.name: c.pollution for c in countries}
        self.ecosystem_health = 60
        self.alarm_level = 0
        self.lock = threading.Lock()

    def update_pollution(self):
        try:
            global_pollution = sum(c.pollution for c in self.countries) / len(self.countries)
            regional_pollution = {}
            with self.lock:
                self.global_pollution = global_pollution
                for country in self.countries:
                    neighbors = [c for c in self.countries if c != country]
                    regional_pollution[country.name] = country.pollution + sum(c.pollution * 0.1 for c in neighbors)
                    if regional_pollution[country.name] > 50:
                        country.happiness = max(0, country.happiness - 5)
                        country.resources['forest'] = max(0, country.resources['forest'] - 10)
                        country.rebellion_risk += 0.05
                        safe_print(f"{country.name} suffers from high regional pollution, happiness -5, forest -10, rebellion risk +0.05")
                self.regional_pollution = regional_pollution
                self.ecosystem_health = max(0, min(100, self.ecosystem_health - int(self.global_pollution / 5)))
                safe_print(f"Global pollution: {self.global_pollution:.1f}, Ecosystem health: {self.ecosystem_health}")
        except Exception as e:
            safe_print(f"Error in update_pollution: {str(e)}", exception=True)

    def sound_alarm(self):
        try:
            with self.lock:
                thresholds = [30, 50, 70]
                for i, threshold in enumerate(thresholds, 1):
                    if self.global_pollution > threshold and self.alarm_level < i:
                        self.alarm_level = i
                        safe_print(f"Environment alarm triggered! Level {self.alarm_level}")
                        return
        except Exception as e:
            safe_print(f"Error in sound_alarm: {str(e)}", exception=True)

    def trigger_disasters(self):
        try:
            with self.lock:
                if self.alarm_level >= 1 or random.random() < 0.1:
                    worst_country = max(self.countries, key=lambda c: self.regional_pollution[c.name])
                    multiplier = 2 if worst_country.infrastructure_level < 50 else (0.5 if worst_country.infrastructure_level > 70 else 1)
                    worst_country.population = int(worst_country.population * (1 - 0.05 * multiplier))
                    worst_country.happiness = max(0, worst_country.happiness - 10 * multiplier)
                    worst_country.rebellion_risk += 0.05 * multiplier
                    safe_print(f"{worst_country.name} hit by disease, population -{5 * multiplier}%, happiness -{10 * multiplier}, rebellion risk +{0.05 * multiplier}")
                if self.alarm_level >= 2 or random.random() < 0.05:
                    target = random.choice(self.countries)
                    multiplier = 2 if target.infrastructure_level < 50 else (0.5 if target.infrastructure_level > 70 else 1)
                    target.population = max(0, target.population - int(5000 * multiplier))
                    target.production = max(0, target.production * (1 - 0.2 * multiplier))
                    target.happiness = max(0, target.happiness - 5 * multiplier)
                    safe_print(f"{target.name} hit by earthquake, population -{5000 * multiplier}, production -{20 * multiplier}%, happiness -{5 * multiplier}")
                if self.alarm_level >= 3 or random.random() < 0.02:
                    worst_countries = sorted(self.countries, key=lambda c: self.regional_pollution[c.name], reverse=True)[:2]
                    for country in worst_countries:
                        multiplier = 2 if country.infrastructure_level < 50 else (0.5 if country.infrastructure_level > 70 else 1)
                        country.resources['forest'] = max(0, country.resources['forest'] - int(20 * multiplier))
                        country.money = int(country.money * (1 - 0.1 * multiplier))
                        country.happiness = max(0, country.happiness - 5 * multiplier)
                        safe_print(f"{country.name} hit by flood, forest -{20 * multiplier}, money -{10 * multiplier}%, happiness -{5 * multiplier}")
        except Exception as e:
            safe_print(f"Error in trigger_disasters: {str(e)}", exception=True)

class World:
    def __init__(self):
        self.countries = []
        self.global_events = {}
        self.global_events_done = {year: False for year in range(1, 21)}
        self.lock = threading.Lock()

    def simulate_global_events(self, year):
        try:
            with self.lock:
                if self.global_events_done[year]:
                    return
                self.global_events_done[year] = True
            self.global_events['pandemic'] = random.random() < 0.05
            self.global_events['meteor'] = random.random() < 0.1
            self.global_events['economic_crash'] = random.random() < 0.03
            self.global_events['blackout'] = random.random() < 0.04
            safe_print(f"\nYear {year} Global Events:")
            if self.global_events['pandemic']:
                safe_print("- A pandemic has occurred")
                for country in self.countries:
                    country.production *= 0.5
                    country.happiness = max(0, country.happiness - 10)
                    country.pollution += 2
                    country.population = int(country.population * 0.98)
                    self.ecosystem.regional_pollution[country.name] += 2
            if self.global_events['meteor']:
                safe_print("- A meteor struck Earth")
                for country in self.countries:
                    for key in country.resources:
                        country.resources[key] = max(0, country.resources[key] - random.randint(5, 20))
                    country.happiness = max(0, country.happiness - 5)
                    country.pollution += 3
                    country.tech_level = max(1, country.tech_level - 1)
                    self.ecosystem.regional_pollution[country.name] += 3
            if self.global_events['economic_crash']:
                safe_print("- A global economic crash has occurred!")
                for country in self.countries:
                    country.money = int(country.money * 0.7)
                    country.happiness = max(0, country.happiness - 10)
                    country.pollution += 3
                    self.ecosystem.regional_pollution[country.name] += 3
            if self.global_events['blackout']:
                safe_print("- A national blackout has hit multiple countries!")
                for country in self.countries:
                    country.tech_level = max(1, country.tech_level - 1)
                    country.production *= 0.6
                    country.pollution += 2
                    self.ecosystem.regional_pollution[country.name] += 2
            self.ecosystem.update_pollution()
            self.ecosystem.sound_alarm()
            self.ecosystem.trigger_disasters()
        except Exception as e:
            safe_print(f"Error in simulate_global_events (Year {year}): {str(e)}", exception=True)

    def add_country(self, country):
        self.countries.append(country)

    def initialize_ecosystem(self):
        self.ecosystem = Ecosystem(self.countries)

    def simulate_war(self, year):
        try:
            with self.lock:
                if self.global_events_done[year]:
                    return
            potential_wars = []
            for c1 in self.countries:
                for c2 in self.countries:
                    if c1 != c2:
                        tension = c1.tension_score.get(c2.name, 50)
                        if self.ecosystem.global_pollution > 50:
                            tension += 5
                        if tension > 70:
                            potential_wars.append((c1, c2))
            random.shuffle(potential_wars)
            safe_print("\nSimulating Wars:")
            for attacker, defender in potential_wars[:2]:
                tension = attacker.tension_score.get(defender.name, 50)
                state = attacker.agent.get_state(attacker, tension)
                action = attacker.agent.choose_action(attacker.agent.war_q, state)
                if action == 'peace':
                    safe_print(f"{attacker.name} decided not to attack {defender.name} despite high tension")
                    new_state = attacker.agent.get_state(attacker, tension)
                    reward = 1  # Small positive for avoiding war, let learning adjust
                    attacker.agent.update(attacker.agent.war_q, state, action, reward, new_state)
                    continue
                safe_print(f"{attacker.name} decided to attack {defender.name}")
                old_hap_a = attacker.happiness
                old_mon_a = attacker.money
                old_pol_a = attacker.pollution
                old_eco = self.ecosystem.ecosystem_health
                old_reb_a = attacker.rebellion_risk
                attack_score = attacker.population * 0.15 * attacker.tech_level * (1 + attacker.resources['oil'] / 100 + attacker.resources['gas'] / 200)
                defense_score = defender.population * 0.20 * defender.tech_level * (1 + defender.resources['oil'] / 100 + defender.resources['gas'] / 200)
                if attack_score == defense_score:
                    safe_print(f"No result between {attacker.name} and {defender.name} (equal power)")
                    new_state = attacker.agent.get_state(attacker, attacker.tension_score.get(defender.name, 50))
                    reward = -1  # Penalty for inconclusive war
                    attacker.agent.update(attacker.agent.war_q, state, action, reward, new_state)
                    continue
                winner, loser = (attacker, defender) if attack_score > defense_score else (defender, attacker)
                safe_print(f"{winner.name} won a war against {loser.name}")
                for resource in loser.resources:
                    loss = int(loser.resources[resource] * 0.3)
                    loser.resources[resource] = max(0, loser.resources[resource] - loss)
                    winner.resources[resource] += loss
                pop_loss = int(loser.population * 0.05)
                loser.population -= pop_loss
                winner.population -= int(winner.population * 0.02)
                loser.happiness = max(0, loser.happiness - 10)
                winner.happiness = min(100, winner.happiness + 5)
                winner.pollution += 10
                loser.pollution += 10
                winner.rebellion_risk += 0.05
                loser.rebellion_risk += 0.05
                winner.pollution += 2
                loser.pollution += 2
                self.ecosystem.global_pollution += 2
                self.ecosystem.regional_pollution[winner.name] += 12
                self.ecosystem.regional_pollution[loser.name] += 12
                self.ecosystem.ecosystem_health = max(0, self.ecosystem.ecosystem_health - 15)
                winner.update_tension(loser, 10)
                loser.update_tension(winner, 30)
                if random.random() < 0.5:
                    winner.update_tension(loser, -20)
                    loser.update_tension(winner, -20)
                    safe_print(f"{winner.name} and {loser.name} signed a peace agreement")
                new_state = attacker.agent.get_state(attacker, attacker.tension_score.get(defender.name, 50))
                delta_hap = attacker.happiness - old_hap_a
                delta_mon = (attacker.money - old_mon_a) / 1e7
                delta_pol = attacker.pollution - old_pol_a
                delta_eco = self.ecosystem.ecosystem_health - old_eco
                delta_reb = attacker.rebellion_risk - old_reb_a
                reward = delta_hap + delta_mon - delta_pol - abs(delta_eco) * 2 - delta_reb * 10
                if winner == attacker:
                    reward += 10  # Bonus for winning
                else:
                    reward -= 10  # Penalty for losing
                attacker.agent.update(attacker.agent.war_q, state, action, reward, new_state)
        except Exception as e:
            safe_print(f"Error in simulate_war (Year {year}): {str(e)}", exception=True)

class Country:
    def __init__(self, name):
        self.name = name
        self.population = random.randint(10_000_000, 80_000_000)
        self.resources = {'oil': 100, 'coal': 100, 'gas': 100, 'forest': 100}
        self.natural_disaster_risk = random.uniform(0, 1)
        self.government = random.choice(['right', 'left'])
        self.ideology_score = random.randint(20, 60) if self.government == 'right' else random.randint(-60, -20)
        self.money = random.randint(100_000_000, 1_000_000_000)
        self.military_power = random.randint(50, 300)
        self.happiness = 70
        self.tech_level = random.randint(1, 5)
        self.education_level = random.randint(1, 5)
        self.pollution = random.randint(10, 20)
        self.production = 100
        self.investments = {'economy': 0, 'environment': 0, 'infrastructure': 0}
        self.infrastructure_level = 50
        self.rebellion_risk = 0
        self.year = 0
        self.has_rebelled_this_year = False
        self.tension_score = {}
        self.diplomatic_relations = {}
        self.environment_agreement = 0
        self.agent = None  # To be assigned

    def get_diplomatic_status(self, other):
        tension = self.tension_score.get(other.name, 50)
        if tension < 30:
            return 'friendly'
        elif tension > 70:
            return 'hostile'
        return 'neutral'

    def update_tension(self, partner, change):
        try:
            self.tension_score[partner.name] = min(100, max(0, self.tension_score.get(partner.name, 50) + change))
            safe_print(f"{self.name}'s tension with {partner.name}: {self.tension_score[partner.name]} ({self.get_diplomatic_status(partner)})")
        except Exception as e:
            safe_print(f"Error in update_tension for {self.name}: {str(e)}", exception=True)

    def join_environment_agreement(self):
        try:
            if self.environment_agreement == 1:
                return True
            state = self.agent.get_state(self)
            action = self.agent.choose_action(self.agent.agree_q, state)
            old_hap = self.happiness
            old_mon = self.money
            old_pol = self.pollution
            old_eco = world.ecosystem.ecosystem_health
            old_reb = self.rebellion_risk
            if action == 'join':
                self.environment_agreement = 1
                self.pollution = max(0, self.pollution - 10)
                self.money = int(self.money * 0.95)
                with world.ecosystem.lock:
                    world.ecosystem.ecosystem_health = min(100, world.ecosystem.ecosystem_health + 5)
                for other in world.countries:
                    if other != self and other.environment_agreement:
                        self.update_tension(other, -5)
                        other.update_tension(self, -5)
                        self.ideology_score = (self.ideology_score + other.ideology_score) // 2
                        other.ideology_score = self.ideology_score
                safe_print(f"{self.name} decided to sign environment agreement, pollution -10, ecosystem health +5, ideology aligned")
                success = True
            else:
                self.pollution += 5
                with world.ecosystem.lock:
                    world.ecosystem.regional_pollution[self.name] += 5
                self.happiness = max(0, self.happiness - 2)
                self.rebellion_risk += 0.02
                safe_print(f"{self.name} decided to refuse environment agreement, pollution +5, happiness -2, rebellion risk +0.02")
                success = False
            new_state = self.agent.get_state(self)
            delta_hap = self.happiness - old_hap
            delta_mon = (self.money - old_mon) / 1e7
            delta_pol = self.pollution - old_pol
            delta_eco = world.ecosystem.ecosystem_health - old_eco
            delta_reb = self.rebellion_risk - old_reb
            reward = delta_hap + delta_mon - delta_pol / 10 + delta_eco - delta_reb * 10
            self.agent.update(self.agent.agree_q, state, action, reward, new_state)
            return success
        except Exception as e:
            safe_print(f"Error in join_environment_agreement for {self.name}: {str(e)}", exception=True)
            return False

    def trade_resources(self, partner):
        try:
            if partner == self or world.ecosystem.ecosystem_health < 30:
                return
            resource_needs = {
                'oil': 30 - self.resources['oil'],
                'coal': 20 - self.resources['coal'],
                'gas': 20 - self.resources['gas'],
                'forest': 50 - self.resources['forest']
            }
            resource = max(resource_needs, key=resource_needs.get)
            if resource_needs[resource] <= 0 or partner.resources[resource] < 10:
                safe_print(f"No suitable trade resource between {self.name} and {partner.name}")
                return
            amount = min(random.randint(5, 20), partner.resources[resource])
            if partner.money < amount * 1000:
                safe_print(f"Trade failed: {partner.name} lacks funds")
                return
            relation = 100 - abs(self.ideology_score - partner.ideology_score)
            trade_chance = 0.5 + relation / 200
            if self.get_diplomatic_status(partner) == 'friendly':
                trade_chance += 0.1
            if random.random() > trade_chance:
                safe_print(f"Trade rejected between {self.name} and {partner.name}")
                self.update_tension(partner, 5)
                partner.update_tension(self, 5)
                return
            self.resources[resource] += amount
            partner.resources[resource] -= amount
            self.money -= amount * 1000
            partner.money += amount * 1000
            pollution_increase = {'oil': 4, 'coal': 6, 'gas': 2, 'forest': 1}
            self.pollution += pollution_increase[resource]
            with world.ecosystem.lock:
                world.ecosystem.regional_pollution[self.name] += pollution_increase[resource]
            safe_print(f"{self.name} traded {amount} {resource} from {partner.name}, pollution +{pollution_increase[resource]}")
            self.update_tension(partner, -5)
            partner.update_tension(self, -5)
        except Exception as e:
            safe_print(f"Error in trade_resources for {self.name}: {str(e)}", exception=True)

    def collect_taxes(self):
        try:
            tax_rate = 0.05 if self.government == 'right' else 0.10
            tax_income = int(self.population * tax_rate)
            if self.government == 'right' and self.infrastructure_level > 70:
                tax_income = int(tax_income * 1.10)
                safe_print(f"{self.name} benefits from high infrastructure, tax income +10%")
            happiness_loss = 2 if self.government == 'right' else 5
            if world.ecosystem.global_pollution > 50:
                happiness_loss += 3
                safe_print(f"{self.name} suffers from high global pollution, extra happiness loss +3")
            self.money += tax_income
            self.happiness = max(0, self.happiness - happiness_loss)
            safe_print(f"{self.name} collected {tax_income} in taxes, happiness decreased by {happiness_loss}")
        except Exception as e:
            safe_print(f"Error in collect_taxes for {self.name}: {str(e)}", exception=True)

    def make_investment_decision(self):
        try:
            if self.money < 10_000_000:
                safe_print(f"{self.name} has insufficient funds for investment (money: {self.money}).")
                return
            state = self.agent.get_state(self)
            action = self.agent.choose_action(self.agent.invest_q, state)
            target_area = action
            investment_amount = int(self.money * 0.05)
            if investment_amount < 5_000:
                safe_print(f"{self.name} has insufficient funds for investment (amount: {investment_amount}).")
                return
            old_hap = self.happiness
            old_mon = self.money
            old_pol = self.pollution
            old_eco = world.ecosystem.ecosystem_health
            old_reb = self.rebellion_risk
            self.money -= investment_amount
            self.investments[target_area] += investment_amount
            efficiency = 0.5 if world.ecosystem.ecosystem_health < 30 else 1.0
            if self.happiness > 70:
                efficiency *= 1.2
                safe_print(f"{self.name} benefits from high happiness, investment efficiency +20%")
            elif self.happiness < 30:
                efficiency *= 0.8
                safe_print(f"{self.name} suffers from low happiness, investment efficiency -20%")
            safe_print(f"{self.name} invested {investment_amount} in {target_area} (efficiency: {efficiency:.2f})")
            if target_area == 'economy':
                production_increase = 10 * efficiency if self.government == 'right' else 12 * efficiency
                pollution_increase = 7 * efficiency if self.government == 'right' else 5 * efficiency
                money_increase = 0.07 * efficiency if self.government == 'right' else 0.05 * efficiency
                self.production += production_increase
                self.pollution += pollution_increase
                with world.ecosystem.lock:
                    world.ecosystem.regional_pollution[self.name] += pollution_increase
                self.money = int(self.money * (1 + money_increase))
                self.resources['oil'] += int(5 * efficiency)
                self.resources['coal'] += int(5 * efficiency)
                self.resources['gas'] += int(3 * efficiency)
                safe_print(f"{self.name} boosted resources: +{5 * efficiency:.1f} oil, +{5 * efficiency:.1f} coal, +{3 * efficiency:.1f} gas")
                if self.government == 'left':
                    self.happiness = max(0, self.happiness - 2 * efficiency)
                    safe_print(f"{self.name}'s production increased to {self.production:.1f}, pollution +{pollution_increase:.1f}, money +{money_increase*100:.1f}%, happiness -{2 * efficiency:.1f}")
                else:
                    safe_print(f"{self.name}'s production increased to {self.production:.1f}, pollution +{pollution_increase:.1f}, money +{money_increase*100:.1f}%")
            elif target_area == 'environment':
                pollution_decrease = 10 * efficiency if self.government == 'right' else 12 * efficiency
                eco_health_increase = 3 * efficiency if self.government == 'right' else 7 * efficiency
                self.pollution = max(0, self.pollution - pollution_decrease)
                with world.ecosystem.lock:
                    world.ecosystem.regional_pollution[self.name] = max(0, world.ecosystem.regional_pollution[self.name] - pollution_decrease)
                    world.ecosystem.ecosystem_health = min(100, world.ecosystem.ecosystem_health + eco_health_increase)
                    world.ecosystem.global_pollution = max(0, world.ecosystem.global_pollution - 2 * efficiency)
                self.happiness = min(100, self.happiness + 5 * efficiency)
                self.money = int(self.money * (1 + 0.02 * efficiency))
                self.resources['forest'] += int(5 * efficiency)
                safe_print(f"{self.name} restored forests: +{5 * efficiency:.1f}")
                safe_print(f"{self.name}'s pollution decreased to {self.pollution:.1f}, global pollution -{2 * efficiency:.1f}, ecosystem health +{eco_health_increase:.1f}, happiness +{5 * efficiency:.1f}, money +{2 * efficiency:.1f}%")
            elif target_area == 'infrastructure':
                infra_increase = 25 * efficiency if self.government == 'right' else 15 * efficiency
                rebellion_decrease = 0.03 * efficiency if self.government == 'right' else 0.02 * efficiency
                self.infrastructure_level = min(100, self.infrastructure_level + infra_increase)
                self.happiness = min(100, self.happiness + 4 * efficiency)
                self.rebellion_risk = max(0, self.rebellion_risk - rebellion_decrease)
                safe_print(f"{self.name}'s infrastructure_level increased to {self.infrastructure_level:.1f}, happiness +{4 * efficiency:.1f}, rebellion risk -{rebellion_decrease:.2f}")
            new_state = self.agent.get_state(self)
            delta_hap = self.happiness - old_hap
            delta_mon = (self.money - old_mon) / 1e7
            delta_pol = self.pollution - old_pol
            delta_eco = world.ecosystem.ecosystem_health - old_eco
            delta_reb = self.rebellion_risk - old_reb
            reward = delta_hap + delta_mon - delta_pol + delta_eco * 0.5 - delta_reb * 10
            self.agent.update(self.agent.invest_q, state, action, reward, new_state)
        except Exception as e:
            safe_print(f"Error in make_investment_decision for {self.name}: {str(e)}", exception=True)

    def simulate_turn(self):
        try:
            self.year += 1
            self.population += int(self.population * 0.01)
            self.production += self.tech_level * self.education_level * 0.1
            self.money += int(self.production * 1000)
            safe_print(f"{self.name} economic growth: production {self.production:.1f}, income {int(self.production * 1000)}")
            if self.production > 100:
                oil_consumed = min(5, self.resources['oil'])
                coal_consumed = min(3, self.resources['coal'])
                gas_consumed = min(2, self.resources['gas'])
                self.resources['oil'] = max(0, self.resources['oil'] - oil_consumed)
                self.resources['coal'] = max(0, self.resources['coal'] - coal_consumed)
                self.resources['gas'] = max(0, self.resources['gas'] - gas_consumed)
                self.pollution += oil_consumed * 1.5 + coal_consumed * 2 + gas_consumed * 0.5
                with world.ecosystem.lock:
                    world.ecosystem.regional_pollution[self.name] += oil_consumed * 1.5 + coal_consumed * 2 + gas_consumed * 0.5
                safe_print(f"{self.name} consumed {oil_consumed} oil, {coal_consumed} coal, {gas_consumed} gas, pollution +{oil_consumed * 1.5 + coal_consumed * 2 + gas_consumed * 0.5:.1f}")
            if self.resources['oil'] == 0:
                self.production *= 0.7
                self.happiness = max(0, self.happiness - 10)
                self.rebellion_risk += 0.1
                safe_print(f"{self.name} has run out of oil! Production -30%, happiness -10, rebellion risk +0.1")
            if self.resources['coal'] == 0:
                self.production *= 0.8
                self.happiness = max(0, self.happiness - 5)
                safe_print(f"{self.name} has run out of coal! Production -20%, happiness -5")
            if self.resources['gas'] == 0:
                self.production *= 0.9
                self.money -= 5000
                safe_print(f"{self.name} has run out of gas! Production -10%, money -5000")
            if self.resources['forest'] > 70:
                self.happiness = min(100, self.happiness + 3)
                with world.ecosystem.lock:
                    world.ecosystem.ecosystem_health = min(100, world.ecosystem.ecosystem_health + 1)
                safe_print(f"{self.name}'s forests boost happiness +3, ecosystem health +1")
            elif self.resources['forest'] < 30:
                self.happiness = max(0, self.happiness - 3)
                self.rebellion_risk += 0.05
                safe_print(f"{self.name}'s low forests reduce happiness -3, rebellion risk +0.05")
            self.resources['forest'] += 2
            if self.government == 'left':
                for k in self.resources:
                    self.resources[k] += 3
                safe_print(f"{self.name}'s left government boosts all resources +3")
            else:
                self.resources['oil'] += 2
                self.resources['coal'] += 2
                safe_print(f"{self.name}'s right government boosts oil +2, coal +2")
            if self.production > 100:
                self.pollution += 3
                with world.ecosystem.lock:
                    world.ecosystem.regional_pollution[self.name] += 3
            if world.ecosystem.ecosystem_health < 30:
                self.happiness = max(0, self.happiness - 5)
                self.natural_disaster_risk += 0.2
                self.rebellion_risk += 0.05
                safe_print(f"{self.name} suffers from poor ecosystem health, happiness -5, disaster risk +0.2, rebellion risk +0.05")
            elif world.ecosystem.ecosystem_health > 70:
                happiness_increase = 5 if self.government == 'right' else 7
                self.happiness = min(100, self.happiness + happiness_increase)
                self.money = int(self.money * 1.05)
                safe_print(f"{self.name} benefits from healthy ecosystem, happiness +{happiness_increase}, money +5%")
            if self.year % 4 == 0 and random.random() < 0.3:
                self.happiness = min(100, self.happiness + 5)
                self.rebellion_risk = max(0, self.rebellion_risk - 2)
                self.production *= 1.1
                safe_print(f"{self.name} enjoyed a sports year! Happiness and productivity rose.")
            if self.education_level < 4 and random.random() < 0.2:
                student_loss = int(self.population * 0.01)
                self.population -= student_loss
                self.happiness = max(0, self.happiness - 2)
                safe_print(f"{self.name} lost {student_loss} young people to education migration.")
            if self.tech_level < 5 and random.random() < 0.15:
                tech_loss = int(self.population * random.uniform(0.03, 0.07))
                self.population -= tech_loss
                self.happiness = max(0, self.happiness - 5)
                safe_print(f"{self.name} lost {tech_loss} people to tech migration.")
            self.collect_taxes()
            trade_partner = random.choice([c for c in world.countries if c != self])
            self.trade_resources(trade_partner)
            self.join_environment_agreement()
            self.make_investment_decision()
            if self.year % 4 == 0:
                if self.happiness > 50:
                    safe_print(f"{self.name} government remains {self.government} (happiness: {self.happiness})")
                else:
                    self.government = 'left' if self.government == 'right' else 'right'
                    self.ideology_score = -self.ideology_score
                    self.happiness = 70
                    safe_print(f"{self.name} changed government to {self.government}, ideology {self.ideology_score}, happiness 70")
            if self.happiness < 20 and not self.has_rebelled_this_year:
                self.rebellion()
            if self.happiness < 0:
                self.happiness = 0
            self.has_rebelled_this_year = False
            safe_print(f"{self.name} - Year {self.year} | Pop: {self.population} | Happy: {self.happiness} | Gov: {self.government}")
            time.sleep(1)
        except Exception as e:
            safe_print(f"Error in simulate_turn for {self.name}: {str(e)}", exception=True)

    def rebellion(self):
        try:
            safe_print(f"{self.name} has a rebellion!")
            self.population = int(self.population * 0.9)
            self.military_power = int(self.military_power * 0.5)
            self.money = int(self.money * 0.5)
            if random.random() < 0.25:
                self.government = 'left' if self.government == 'right' else 'right'
                self.ideology_score = -self.ideology_score
                self.happiness = 70
                safe_print(f"{self.name}'s rebellion succeeded. New government: {self.government}, happiness reset to 70")
            else:
                self.happiness = random.randint(30, 40)
                safe_print(f"{self.name}'s rebellion failed. Happiness adjusted to {self.happiness}")
        except Exception as e:
            safe_print(f"Error in rebellion for {self.name}: {str(e)}", exception=True)

def save_to_database(countries):
    try:
        with db_lock:
            conn = sqlite3.connect("World_simulator.db")
            cursor = conn.cursor()
            for country in countries:
                cursor.execute("""
                INSERT INTO countries (
                    name, population, happiness, production, year,
                    government, tech_level, education_level, military_power,
                    money, pollution, rebellion_risk,
                    oil, coal, gas, forest,
                    invest_economy, invest_environment, invest_infrastructure,
                    infrastructure_level, ideology_score, environment_agreement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    country.name, country.population, country.happiness, country.production, country.year,
                    country.government, country.tech_level, country.education_level, country.military_power,
                    country.money, country.pollution, country.rebellion_risk,
                    country.resources['oil'], country.resources['coal'],
                    country.resources['gas'], country.resources['forest'],
                    country.investments['economy'], country.investments['environment'],
                    country.investments['infrastructure'], country.infrastructure_level,
                    country.ideology_score, country.environment_agreement
                ))
            conn.commit()
            cursor.execute("SELECT * FROM countries")
            rows = cursor.fetchall()
            conn.close()
            safe_print("Database save completed successfully")
            return rows
    except Exception as e:
        safe_print(f"Error in save_to_database: {str(e)}", exception=True)
        return []

def simulate_world(world, years=10):
    try:
        for year in range(1, years + 1):
            safe_print(f"Processing Year {year}")
            world.simulate_global_events(year)
            world.simulate_war(year)
            with ThreadPoolExecutor(max_workers=len(world.countries)) as executor:
                futures = [executor.submit(country.simulate_turn) for country in world.countries]
                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        safe_print(f"Thread error: {str(e)}", exception=True)
            safe_print(f"Year {year} completed")
    except Exception as e:
        safe_print(f"Error in simulate_world: {str(e)}", exception=True)
    finally:
        safe_print("Simulation finished")

names = ['Sofialand', 'Jimenara', 'Paulovia', 'Claraton', 'Justoria']
agents = {name: RLAgent() for name in names}
episodes = 20  # Number of training episodes; increase for better learning, but longer runtime

for episode in range(episodes):
    safe_print(f"\n=== Episode {episode + 1} ===\n")
    init_database()
    world = World()
    for name in names:
        country = Country(name)
        country.agent = agents[name]
        world.add_country(country)
    world.initialize_ecosystem()
    for country in world.countries:
        for other in world.countries:
            if country != other:
                country.tension_score[other.name] = random.randint(40, 60)  # Reset initial tensions each episode
                country.diplomatic_relations[other.name] = country.get_diplomatic_status(other)
    if episode == 0:
        open("simulation_log.txt", "w", encoding="utf-8").close()
    else:
        with open("simulation_log.txt", "a", encoding="utf-8") as f:
            print("\n=== New Episode ===\n", file=f)
    simulate_world(world, years=10)
    rows = save_to_database(world.countries)

safe_print("\nFINAL STATUS AFTER TRAINING:")
for country in world.countries:
    safe_print(f"{country.name}:")
    safe_print(f"  Population: {country.population}")
    safe_print(f"  Happiness: {country.happiness}")
    safe_print(f"  Government: {country.government}")
    safe_print(f"  Tech Level: {country.tech_level}")
    safe_print(f"  Education Level: {country.education_level}")
    safe_print(f"  Pollution: {country.pollution}")
    safe_print(f"  Production: {country.production}")
    safe_print(f"  Money: {country.money}")
    safe_print(f"  Military Power: {country.military_power}")
    safe_print(f"  Resources:")
    for resource, value in country.resources.items():
        safe_print(f"    {resource.capitalize()}: {value}")
    safe_print(f"  Infrastructure: {country.infrastructure_level}")
    safe_print(f"  Investments: {country.investments}")
    safe_print(f"  Rebellion Risk: {country.rebellion_risk}")





    

class GameVisualizer:
    def __init__(self, world):
        pygame.init()
        self.width = 1200
        self.height = 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("World Simulation - Age of Empires Style")
        self.world = world
        self.font = pygame.font.SysFont("Arial", 14, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 20, bold=True)
        
        # Renkler
        self.WATER_COLOR = (28, 107, 160)
        self.LAND_COLOR = (34, 139, 34)
        self.COUNTRY_COLORS = {
            'Sofialand': (200, 50, 50),   # Kırmızı
            'Jimenara': (50, 200, 50),    # Yeşil
            'Paulovia': (50, 50, 200),    # Mavi
            'Claraton': (200, 200, 50),   # Sarı
            'Justoria': (200, 50, 200)    # Mor
        }
        
        # Ülkelerin haritadaki sabit konumları (x, y)
        self.positions = {
            'Sofialand': (200, 200),
            'Jimenara': (1000, 200),
            'Paulovia': (600, 400),
            'Claraton': (200, 600),
            'Justoria': (1000, 600)
        }
        
        # Resimler (Basit şekiller yerine sprite kullanılabilir)
        # Burada basit çizimler kullanacağız

    def draw_country(self, country):
        x, y = self.positions[country.name]
        color = self.COUNTRY_COLORS.get(country.name, (255, 255, 255))
        
        # 1. Kirlilik Bulutu (Pollution Cloud)
        # Kirlilik arttıkça etrafındaki gri daire büyür ve koyulaşır
        pollution_radius = 50 + country.pollution * 2
        pollution_surface = pygame.Surface((pollution_radius*2, pollution_radius*2), pygame.SRCALPHA)
        pygame.draw.circle(pollution_surface, (50, 50, 50, min(150, country.pollution * 5)), (pollution_radius, pollution_radius), pollution_radius)
        self.screen.blit(pollution_surface, (x - pollution_radius, y - pollution_radius))

        # 2. Ana Bina (Kale/Şehir)
        pygame.draw.rect(self.screen, color, (x-30, y-30, 60, 60))
        pygame.draw.rect(self.screen, (0,0,0), (x-30, y-30, 60, 60), 2) # Çerçeve
        
        # İsim
        name_text = self.title_font.render(country.name, True, (255, 255, 255))
        self.screen.blit(name_text, (x - name_text.get_width()//2, y - 55))

        # 3. İstatistik Barları (Health Bar gibi)
        # Mutluluk (Sarı Bar)
        pygame.draw.rect(self.screen, (100, 100, 100), (x-40, y+40, 80, 8))
        pygame.draw.rect(self.screen, (255, 215, 0), (x-40, y+40, 80 * (country.happiness/100), 8))
        
        # Nüfus (Mavi Bar - Göreceli)
        pop_percent = min(1.0, country.population / 100_000_000)
        pygame.draw.rect(self.screen, (100, 100, 100), (x-40, y+50, 80, 8))
        pygame.draw.rect(self.screen, (0, 191, 255), (x-40, y+50, 80 * pop_percent, 8))

        # 4. Detaylı Bilgiler
        info_y = y + 65
        infos = [
            f"Money: ${country.money // 1_000_000}M",
            f"Oil: {country.resources['oil']} | Coal: {country.resources['coal']}",
            f"Gov: {country.government}",
            f"Infra: {country.infrastructure_level:.0f}"
        ]
        
        for info in infos:
            text = self.font.render(info, True, (240, 240, 240))
            self.screen.blit(text, (x - 40, info_y))
            info_y += 15

    def draw_relations(self):
        # Savaş veya Gerginlik Çizgileri
        for country in self.world.countries:
            x1, y1 = self.positions[country.name]
            for other_name, tension in country.tension_score.items():
                if tension > 70: # Yüksek gerginlik veya savaş
                    x2, y2 = self.positions.get(other_name, (0,0))
                    # Kesikli kırmızı çizgi veya kalın kırmızı çizgi
                    pygame.draw.line(self.screen, (255, 0, 0), (x1, y1), (x2, y2), int((tension-70)/5))

    def draw_global_stats(self):
        # Sol üst köşe genel dünya durumu
        pygame.draw.rect(self.screen, (0, 0, 0), (10, 10, 300, 120))
        pygame.draw.rect(self.screen, (255, 255, 255), (10, 10, 300, 120), 2)
        
        try:
            eco_health = self.world.ecosystem.ecosystem_health
            glob_poll = self.world.ecosystem.global_pollution
        except:
            eco_health = 100
            glob_poll = 0
            
        stats = [
            f"Year: {self.world.countries[0].year if self.world.countries else 0}",
            f"Global Pollution: {glob_poll:.2f}",
            f"Ecosystem Health: {eco_health:.2f}",
            "Red Lines: High Tension/War",
            "Grey Circle: Pollution Level"
        ]
        
        for i, stat in enumerate(stats):
            text = self.font.render(stat, True, (255, 255, 255))
            self.screen.blit(text, (20, 20 + i*20))

    def update(self):
        # Arka plan
        self.screen.fill(self.WATER_COLOR)
        
        # Harita efekti (Basit bir yeşil alan)
        # Daha karmaşık bir harita resmi de yüklenebilir
        # pygame.draw.ellipse(self.screen, self.LAND_COLOR, (50, 50, 1100, 700))

        # İlişkileri çiz (Altta kalsın)
        self.draw_relations()

        # Ülkeleri çiz
        for country in self.world.countries:
            self.draw_country(country)
            
        # Global statları çiz
        self.draw_global_stats()
        
        pygame.display.flip()

    def run(self):
        running = True
        clock = pygame.time.Clock()
        
        # Simülasyonu ayrı bir thread'de başlatıyoruz ki GUI donmasın
        sim_thread = threading.Thread(target=run_simulation_thread, args=(self.world,))
        sim_thread.daemon = True # Ana program kapanınca bu da kapansın
        sim_thread.start()

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            
            self.update()
            clock.tick(60) # 60 FPS

        pygame.quit()

# Mevcut simulate_world fonksiyonunu thread uyumlu hale getirmek için wrapper
def run_simulation_thread(world_obj):
    # Senin döngünü burada çağırıyoruz
    # episodes döngüsü yerine tek bir sürekli akış veya episode döngüsü:
    global episodes
    for episode in range(episodes):
        simulate_world(world_obj, years=20)
        # Episode bitince resetleme mantığı eklenebilir
        time.sleep(2) 
        # (Not: Senin kodundaki simulate_world içindeki init kısımlarını buraya uyarlamak gerekebilir)

# --- ANA ÇALIŞTIRMA KISMI ---

if __name__ == "__main__":
    # Veritabanı ve Agent Hazırlığı
    init_database()
    names = ['Sofialand', 'Jimenara', 'Paulovia', 'Claraton', 'Justoria']
    agents = {name: RLAgent() for name in names}
    episodes = 20
    
    # Dünyayı Kur
    world = World()
    for name in names:
        country = Country(name)
        country.agent = agents[name]
        world.add_country(country)
    world.initialize_ecosystem()
    
    # İlişkileri başlat
    for country in world.countries:
        for other in world.countries:
            if country != other:
                country.tension_score[other.name] = random.randint(40, 60)

    # Görselleştirmeyi Başlat
    viz = GameVisualizer(world)
    viz.run()
    
