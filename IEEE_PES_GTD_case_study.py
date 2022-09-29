def test_case4():
    """
    Creates the test case used in the paper submitted in IEEE PES GT&D.
    Returns the network in pandapower format. Includes a new flexibility dataframe which contains all the
    flexibility information of the network.

    Created by Papazoglou Georgios in August 2022.
    """
    import pandas as pd
    import numpy as np
    import pandapower.networks as pn  # run 'pip install pandapower' in the console to install pandapower

    net = pn.create_cigre_network_mv(with_der="pv_wind")  # import the template network
    net.switch['closed'] = True  # close all the switches of the network
    net.bus['max_vm_pu'] = 1.05  # set upper voltage limits on each bus
    net.bus['min_vm_pu'] = 0.95  # set lower voltage limits on each bus
    net.line['max_loading_percent'] = 100  # set the maximum loading percentage of all lines
    net.line['c_nf_per_km'] = 0
    net.sgen['p_mw'].iloc[:-1] *= 30  # increase the generation on all PVs for a larger FOR

    # set which loads are dispatchable, assuming one FPU per bus at most
    net.load['controllable'] = [True, False, False, False, False, False, False, False, True, False, False, False, False,
                                False, False, False, True, True]  # 4 dispatchable, the rest non-dispatchable

    # create the net.flexibility DataFrame that contains the flexibility values for all FPUs
    # assume that wind turbines and PVs are operating at their maximum output and can regulate it all the way to zero
    # assume that wind turbines can work in the range of cosφ 0.95 ind. to 0.95 cap.
    # assume that PVs can work in the range of cosφ 0.9 ind. to 0.9 cap.
    number_of_dispatchable_loads = (net.load['controllable'] == True).sum()

    # element: id of pp element
    # et: type of pp element
    # up(down)_quantity: amount of upward(downward) flexibility (in MW)
    # up(down)_cost: cost of upward(downward) flexibility (in EUR/MW)
    # FPU_type: indicates the capability chart of each element
    # FPU_info: contains the info needed to create the capability chart (object type dict in case more info needs to be
    # passed along, and to accommodate for expansion to new FPU types)
    # p_setpoint: the active power setpoint of the FPU
    # q_setpoint: the reactive power setpoint of the FPU
    # bus: the bus where the FPU is located
    # The following convention is assumed: upward flexibility increases the net injection (increase in generation or
    # decrease in consumption), and the opposite for downward flexibility.

    net.flexibility = pd.DataFrame(columns=['element', 'et', 'up_quantity', 'up_cost', 'down_quantity', 'down_cost',
                                            'FPU_type', 'FPU_info'],
                                   index=list(range(number_of_dispatchable_loads + len(net.sgen))))
    # controllable loads
    net.flexibility['element'].loc[:number_of_dispatchable_loads-1] = net.load[net.load['controllable']].index
    net.flexibility['et'].loc[:number_of_dispatchable_loads-1] = 'load'

    # loads can increase/decrease their offtake by half of their setpoint
    net.flexibility['up_quantity'].loc[:number_of_dispatchable_loads-1] = \
        (net.load['p_mw'][net.load['controllable']]/2).to_list()
    net.flexibility['down_quantity'].loc[:number_of_dispatchable_loads-1] = \
        (net.load['p_mw'][net.load['controllable']]/2).to_list()
    net.flexibility['FPU_type'].loc[:number_of_dispatchable_loads - 1] = 'load'
    # calculate cosφ of controllable loads
    angle = np.arctan(net.load['q_mvar'][net.load['controllable']] / net.load['p_mw'][net.load['controllable']])
    pfs = np.cos(angle).to_list()  # power factor
    net.flexibility['FPU_info'].loc[:number_of_dispatchable_loads - 1] = [{'pf': pf} for pf in pfs]

    # PVs
    net.flexibility['element'].loc[number_of_dispatchable_loads:] = net.sgen.index
    net.flexibility['et'].loc[number_of_dispatchable_loads:] = 'sgen'
    net.flexibility['up_quantity'].loc[number_of_dispatchable_loads:] = (1.1*net.sgen['p_mw']).to_list()
    net.flexibility['down_quantity'].loc[number_of_dispatchable_loads:] = (net.sgen['p_mw']).to_list()
    number_of_pvs = 0
    number_of_box = 9
    assert number_of_box + number_of_pvs == 9  # for debugging
    types = ['PV']*number_of_pvs
    types.extend(['Box']*number_of_box)
    net.flexibility['FPU_type'].loc[number_of_dispatchable_loads:] = types

    # set the power factor to 0.9 for PVs and 0.95 for wind farms
    pfs = [0.9]*number_of_pvs
    extra_info = [{'pf': pf} for pf in pfs]
    np.random.seed(0)
    fuzz = np.random.random(number_of_box).round(3)
    # fuzz = np.zeros(number_of_box)
    extra_info.extend([{'q_min': -1 - f, 'q_max': 1 + f} for f in fuzz])
    net.flexibility['FPU_info'].loc[number_of_dispatchable_loads:] = extra_info

    # assign random costs to FPUs
    np.random.seed(1)  # for replicability
    net.flexibility['up_cost'] = (90 + 20*np.random.random(len(net.flexibility)).round(3))

    np.random.seed(2)
    net.flexibility['down_cost'] = (100 - 20*np.random.random(len(net.flexibility)).round(3))

    # add the setpoints of each element to the flexibility dataframe for convenience
    net.flexibility['p_setpoint'] \
        = net.flexibility.apply(func=lambda x: getattr(net, x['et']).loc[x['element']]['p_mw'], axis=1)

    # invert the sign on the loads to indicate power offtake
    net.flexibility['p_setpoint'][net.flexibility['et'] == 'load'] *= -1

    net.flexibility['q_setpoint'] \
        = net.flexibility.apply(func=lambda x: getattr(net, x['et']).loc[x['element']]['q_mvar'], axis=1)

    # invert the sign on the loads to indicate reactive power consumption
    net.flexibility['q_setpoint'][net.flexibility['et'] == 'load'] *= -1

    # add the bus in which each FPU is located for convenience
    net.flexibility['bus'] \
        = net.flexibility.apply(func=lambda x: getattr(net, x['et']).loc[x['element']]['bus'], axis=1)

    return net