from data_feed import generate_simulated_alert

def main():
    alert = generate_simulated_alert()
    print('GENERATED', alert['id'], alert['source'], alert['type'])

if __name__ == '__main__':
    main()
